"""PII patterns and redaction shared by the sanitiser (before state) and the PII scan (after the run).

Three layers, because commenters mention people who never appear as an author on the page:
1. exact names collected from the page's comment author blocks and JSON-LD persons;
2. a capitalised word straight after a greeting ("Hi Katie", "Thanks, Sam") is treated as a name;
3. a first-name gazetteer (gender-guesser's nam_dict, used only as a list of names), skipping
   words that are common English or food vocabulary, so "June" and "Cherry" are left alone.
Plus regexes for emails (including "name at domain dot com"), links, @handles and phone numbers.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
OBFUSCATED_EMAIL_RE = re.compile(
    r"\b[\w.+-]+\s*(?:\(at\)|\[at\]|\s+at\s+)\s*[\w-]+\s*(?:\(dot\)|\[dot\]|\s+dot\s+)\s*"
    r"(?:com|net|org|edu|gov|co|us|uk|ca|info|biz|me)\b",
    re.I,
)
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|net|org|co\.uk|blog)(?:/\S*)?\b", re.I)
HANDLE_RE = re.compile(r"(?<![\w@])@(?!(?:type|context|graph|id|value|list|language|vocab)\b)[A-Za-z0-9_.]{2,}")
PHONE_RE = re.compile(
    r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w.])|(?<![\w.])\+\d[\d\s-]{8,}\d(?![\w.])"
)
GREETING_RE = re.compile(
    r"\b((?:Hi|Hey|Hello|Dear|Thanks|Thank you|Thx|Oh|Ok|Okay|Congrats|Bless you)[,!]?\s+)"
    r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?)(?=[\s,.!?:;–—-]|$)"
)

# Words that a greeting is often followed by but that are not names.
NOT_NAMES_AFTER_GREETING = {
    "So", "For", "The", "This", "That", "Everyone", "All", "Again", "You", "Thank", "My", "Wow", "God",
    "Yum", "Yes", "No", "I", "It", "Love", "Great", "Ladies", "Guys", "Friends", "Folks", "There",
}

COMMON_WORD_ZIPF = 4.6  # wordfreq Zipf frequency; >= this means an everyday English word


@lru_cache(maxsize=1)
def first_names() -> frozenset[str]:
    import gender_guesser  # list of ~40k given names, used here only as a gazetteer

    path = Path(gender_guesser.__file__).parent / "data" / "nam_dict.txt"
    names = set()
    with open(path, encoding="iso-8859-1") as fh:
        for line in fh:
            if line.startswith("#") or len(line) < 30:
                continue
            name = line[3:29].strip()
            if name.isalpha() and len(name) >= 3:
                names.add(name)
    return frozenset(names)


@lru_cache(maxsize=1)
def food_vocabulary() -> frozenset[str]:
    from .config import SR28_DIR

    words = set()
    with open(SR28_DIR / "FOOD_DES.txt", encoding="latin-1") as fh:
        for line in fh:
            desc = line.split("^")[2]
            words.update(w.lower() for w in re.findall(r"[A-Za-z]+", desc))
    return frozenset(words)


@lru_cache(maxsize=4096)
def is_gazetteer_name(word: str) -> bool:
    if not (word[:1].isupper() and word[1:].islower() and len(word) >= 3):
        return False
    if word not in first_names():
        return False
    low = word.lower()
    if low in food_vocabulary():
        return False
    from wordfreq import zipf_frequency

    return zipf_frequency(low, "en") < COMMON_WORD_ZIPF


def expand_names(raw_names: set[str]) -> set[str]:
    """Full display names plus their capitalised parts ("Jane Doe" -> Jane Doe, Jane, Doe)."""
    from wordfreq import zipf_frequency

    def common(word: str) -> bool:
        return zipf_frequency(word.lower(), "en") >= COMMON_WORD_ZIPF

    out = set()
    for n in raw_names:
        n = re.sub(r"\s+", " ", n).strip()
        if len(n) < 2 or (" " not in n and common(n)):
            continue
        out.add(n)
        for part in re.split(r"[\s_.,&/@-]+", n):
            if len(part) >= 3 and part[0].isupper() and not common(part):
                out.add(part)
    return out


def scrub_text(text: str, names: set[str] = frozenset()) -> str:
    text = EMAIL_RE.sub("[email]", text)
    text = OBFUSCATED_EMAIL_RE.sub("[email]", text)
    text = URL_RE.sub("[link]", text)
    text = HANDLE_RE.sub("[handle]", text)
    text = PHONE_RE.sub("[phone]", text)
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "[name]", text)
    text = GREETING_RE.sub(
        lambda m: m.group(1) + ("[name]" if m.group(2).split()[0] not in NOT_NAMES_AFTER_GREETING else m.group(2)),
        text,
    )
    text = re.sub(r"\b[A-Z][a-z]{2,}\b", lambda m: "[name]" if is_gazetteer_name(m.group(0)) else m.group(0), text)
    return re.sub(r"\s+", " ", text).strip()


def find_pii(text: str, known_names: set[str] = frozenset()) -> list[tuple[str, str]]:
    """Return (kind, match) pairs for anything that looks like PII. Used by the PII scan."""
    hits: list[tuple[str, str]] = []
    for kind, rx in (
        ("email", EMAIL_RE), ("obfuscated_email", OBFUSCATED_EMAIL_RE), ("handle", HANDLE_RE),
        ("phone", PHONE_RE), ("gravatar", re.compile(r"gravatar\.com/\S+", re.I)),
    ):
        hits += [(kind, m.group(0)) for m in rx.finditer(text)]
    for name in known_names:
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
            hits.append(("known_commenter_name", name))
    for m in re.finditer(r"\b[A-Z][a-z]{2,}\b", text):
        if is_gazetteer_name(m.group(0)):
            hits.append(("gazetteer_name", m.group(0)))
    return hits
