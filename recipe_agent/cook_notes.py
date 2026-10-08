"""Cook notes card: what people who made the recipe said, every claim backed by comment ids.

Two backends produce candidate claims:
  * ThemeSummariser (default, deterministic): matches each comment against a fixed set of themes,
    with negation handling ("not too sweet" does not count as "too sweet").
  * GroqSummariser (used when GROQ_API_KEY is set): asks a Groq-hosted model for claims as JSON
    with the comment ids that support each one.

Whatever the backend, `finalize_card` is the single gate: it drops claims whose ids are not real
comment ids, recomputes each count from the ids (the model's own number is never trusted),
drops claims under MIN_SUPPORT, and enforces the word cap in code.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from .config import CARD_WORD_CAP

MIN_SUPPORT = 2  # a claim needs at least this many comments behind it


@dataclass(frozen=True)
class Theme:
    key: str
    label: str  # card wording; the count is appended by the card builder
    pattern: str  # must match inside one first-hand, non-question sentence
    requires: str | None = None  # must also match somewhere in the same comment's report sentences


FIRST_HAND_MADE = (
    r"(\b(i|we|i've|we've|i have|we have)\b[^.!?]{0,40}\b(made|baked|tried|followed (the|this|your) "
    r"(recipe|directions|instructions)|used|did)\b|^(made|baked|followed the recipe|tried)\b|\b(it|they|this|these|cake|pie|cookies|bread|bars)\b[^.!?]{0,20}\b(turned|came) out\b)"
)
POSITIVE = (
    r"(?<!looks )(?<!look )(?<!sounds )(?<!sound )(?<!seems )\b(lov(e|ed|es)|delicious|amazing|perfect(ly)?|great|"
    r"excellent|hit|yum(my)?|best|fantastic|wonderful|awesome|good|tasty|incredible|superb(ly)?|fabulous|moist|well)\b"
)
THEMES = (
    Theme("made_liked", "made it and liked it", FIRST_HAND_MADE, requires=POSITIVE),
    Theme("easy", "called it easy or quick",
          r"(\b(it|this|these|they|recipe|was|were|is|so|super|very|really|way|and)\b\W+(easy|simple|quick)\b|\beasy to (make|follow)\b)"),
    Theme("crowd", "said family or guests enjoyed it",
          r"\b(family|husband|hubby|kids|wife|son|daughter|everyone|guests|party|crowd|co-?workers|friends|they all)\b"
          r"[^.!?]{0,40}\b(lov(ed|es)|enjoyed|liked|devoured|raved|hit|gone)\b"),
    Theme("again", "will make it again or already have",
          r"(make (it|this|these|them) again|again and again|will be making|keeper|go-?to|every (year|christmas|time)|"
          r"tradition|staple|(made|baked) (it|this|these|them) (\d+|two|three|many|several|a few|multiple) times|"
          r"second time|third time)"),
    Theme("substitution", "described a substitution or change they made",
          r"\b(i|we)\b[^.!?]{0,30}\b(substituted|subbed|subbing|swapped|replaced|omitted|left out|reduced|"
          r"cut (back|down)|doubled|halved|used [^.!?]{1,30} (instead|in place)|"
          r"added (some|a little|a bit|extra|more|\d+)\b|added [^.!?]{1,30} to (the|my) (batter|dough|filling|frosting|"
          r"topping|mix|cake|crust|pie|cookies|recipe))\b"),
    Theme("sweetness", "found it too sweet or cut the sugar",
          r"(too sweet|very sweet|less sugar|reduce(d)? the sugar|cut (back|down) (on )?(the )?sugar|half the sugar|overly sweet)"),
    Theme("problem", "reported a problem (flat, dry, sank, runny, crumbly)",
          r"\b(dry(?! ingredients| mix| measuring)|runny|sank|sunk|collapsed|burn(t|ed)|came out flat|spread too|crumbl(es|ed|y)|"
          r"didn.?t work|failed|disappoint\w*|soggy|gummy|greasy|rubbery|bitter|didn.?t set)\b"),
)
QUESTION_THEME = Theme("question", "asked a question", r"\?")
# sentences that talk about plans, wishes or other people's cooking are not first-hand reports
NOT_A_REPORT = re.compile(
    r"\b(can.?t wait|will try|going to (try|make)|gonna (try|make)|plan(ning)? to|want to|would|could|if (i|we)|"
    r"can (i|you|this|it)|have you|do you|did you|my (grand)?(ma|mom|mother|sister|aunt|friend.?s mom)\w*)\b",
    re.I,
)
NEGATION = re.compile(r"\b(not|n't|never|no|wasn.?t|isn.?t|didn.?t|without)\W+(\w+\W+){0,3}$", re.I)
NEGATED_INSIDE = re.compile(r"\b(never|not|n't|didn.?t|haven.?t)\b", re.I)


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]


def _report_sentences(text: str) -> list[str]:
    return [x for x in _sentences(text) if not x.rstrip().endswith("?") and not NOT_A_REPORT.search(x)]


def _matches(pattern: str, sentences: list[str]) -> bool:
    for sentence in sentences:
        for m in re.finditer(pattern, sentence, re.I):
            if NEGATED_INSIDE.search(m.group(0)):
                continue  # "I've never tried", "we did not make"
            if not NEGATION.search(sentence[max(0, m.start() - 40): m.start()]):
                return True
    return False


class ThemeSummariser:
    """Deterministic claims: each theme counts comments with a first-hand sentence matching it."""

    name = "themes-v2"

    def claims(self, comments: list[dict]) -> list[dict]:
        out = []
        reports = {c["comment_id"]: _report_sentences(c["text"]) for c in comments}
        for theme in THEMES:
            ids = [cid for cid, sents in reports.items()
                   if _matches(theme.pattern, sents) and (theme.requires is None or _matches(theme.requires, sents))]
            out.append({"text": theme.label, "comment_ids": ids, "theme": theme.key})
        asked = [c["comment_id"] for c in comments if "?" in c["text"]]
        out.append({"text": QUESTION_THEME.label, "comment_ids": asked, "theme": QUESTION_THEME.key})
        return out


class GroqSummariser:
    """LLM backend on Groq's OpenAI-compatible API. Needs GROQ_API_KEY; GROQ_MODEL overrides the model.

    The model only proposes claims and the comment ids behind them. finalize_card() then drops ids
    that are not real comments, recounts from the ids and applies the word cap, so the model can
    neither inflate a count nor exceed the cap.
    """

    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    SCHEMA = {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "comment_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["text", "comment_ids"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    }
    INSTRUCTIONS = (
        "You summarise reader comments on one recipe. Each comment is prefixed with its id in brackets.\n"
        "Return up to 6 claims about what people who MADE the recipe reported: results, changes they made, "
        "problems, who enjoyed it. Ignore questions, plans to try it, praise of the photo, and other people's "
        "versions. Each claim is a short verb phrase of at most 8 words, with no numbers and no names, for "
        "example 'cut the sugar and liked it'. For each claim list the ids of every comment that supports it. "
        "Use only ids from the list. Reply with JSON only: "
        '{"claims": [{"text": "...", "comment_ids": ["..."]}]}'
    )

    def __init__(self, api_key: str | None = None, model: str | None = None, transport=None, timeout: float = 60.0):
        import httpx

        self.api_key = api_key or os.environ["GROQ_API_KEY"]
        self.model = model or os.environ.get("GROQ_MODEL") or self.DEFAULT_MODEL
        self.http = httpx.Client(timeout=timeout, transport=transport)

    def _post(self, response_format: dict, listing: str) -> dict:
        r = self.http.post(
            self.URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": response_format,
                "messages": [
                    {"role": "system", "content": self.INSTRUCTIONS},
                    {"role": "user", "content": listing},
                ],
            },
        )
        return r

    def claims(self, comments: list[dict]) -> list[dict]:
        listing = "\n".join(f"[{c['comment_id']}] {c['text']}" for c in comments)
        r = self._post({"type": "json_schema",
                        "json_schema": {"name": "cook_notes", "schema": self.SCHEMA, "strict": True}}, listing)
        if r.status_code == 400:  # model without structured-output support: plain JSON mode
            r = self._post({"type": "json_object"}, listing)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        claims = data.get("claims", []) if isinstance(data, dict) else []
        return [c for c in claims if isinstance(c, dict)]


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _claim_sentence(claim: dict, total: int) -> str:
    return f"{claim['count']} of {total} {claim['text']}."


def enforce_word_cap(header: str, claims: list[dict], total: int, cap: int = CARD_WORD_CAP) -> tuple[str, list[dict]]:
    """Add claims (already ordered) while the card stays within `cap` words. Hard guarantee."""
    card, kept = header, []
    for claim in claims:
        candidate = f"{card} {_claim_sentence(claim, total)}"
        if count_words(candidate) > cap:
            continue
        card, kept = candidate, kept + [claim]
    assert count_words(card) <= cap
    return card, kept


def finalize_card(raw_claims: list[dict], comments: list[dict], cap: int = CARD_WORD_CAP) -> tuple[str, list[dict]]:
    valid_ids = {c["comment_id"] for c in comments}
    total = len(comments)
    cleaned = []
    for claim in raw_claims:
        ids = sorted({str(i) for i in claim.get("comment_ids", []) if str(i) in valid_ids}, key=int)
        text = re.sub(r"\s+", " ", str(claim.get("text", ""))).strip().rstrip(".")
        if len(ids) < MIN_SUPPORT or not text:
            continue
        cleaned.append({"text": text, "count": len(ids), "comment_ids": ids})
    # cook reports first (most-supported first); "asked a question" only fills leftover space
    cleaned.sort(key=lambda c: (c["text"] == "asked a question", -c["count"]))
    header = f"Cook notes ({total} comments):"
    return enforce_word_cap(header, cleaned, total, cap)


def get_summariser(name: str = "auto"):
    """"auto" uses Groq when GROQ_API_KEY is set, otherwise the deterministic themes."""
    if name == "groq" or (name == "auto" and os.environ.get("GROQ_API_KEY")):
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("--summariser groq needs GROQ_API_KEY")
        return GroqSummariser()
    return ThemeSummariser()
