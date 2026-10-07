import json

from recipe_agent.config import CARD_WORD_CAP
from recipe_agent.cook_notes import ThemeSummariser, count_words, finalize_card
from recipe_agent.pii import find_pii
from recipe_agent.sanitize import sanitize_page


def test_sanitized_page_has_no_commenter_identity(dal_html):
    page, summary = sanitize_page(dal_html)
    assert summary == {"recipes": 1, "comments": 4}
    for leaked in ("Marcus", "Whitfield", "Priya", "Raman", "dal_lover_88", "Deepika", "gravatar",
                   "marcus.blog", "example.com", "555-123-4567", "example dot com"):
        assert leaked not in page, leaked
    assert "Made this twice, family loved it!" in page
    assert 'data-comment-id="102" data-post-author="1"' in page


def test_jsonld_keeps_only_recipe_fields(dal_html):
    page, _ = sanitize_page(dal_html)
    assert '"review"' not in page and '"author"' not in page and "toor dal" in page


def test_find_pii_flags_known_names_and_patterns():
    kinds = {k for k, _ in find_pii("mail bob@x.org or call (555) 123-4567, by Jane", {"Jane"})}
    assert {"email", "phone", "known_commenter_name"} <= kinds


def _comments(n):
    return [{"comment_id": str(i), "text": t} for i, t in enumerate(
        ["I made it and it was delicious, family loved it", "Made this, so easy and good",
         "Baked it twice, everyone loved it, will make it again", "Is it not too sweet?",
         "I made it with less sugar, perfect", "Turned out great, easy"] * n, start=1)]


def test_card_word_cap_is_enforced_in_code():
    many = [{"text": "a very long claim " * 5 + str(i), "comment_ids": ["1", "2", "3"]} for i in range(20)]
    card, kept = finalize_card(many, _comments(1), cap=CARD_WORD_CAP)
    assert count_words(card) <= CARD_WORD_CAP
    assert 0 < len(kept) < 20


def test_claim_counts_come_from_valid_ids_only():
    raw = [{"text": "liked it", "comment_ids": ["1", "2", "999", "2"]},  # 999 is not a comment
           {"text": "single report", "comment_ids": ["3"]}]  # below minimum support
    card, kept = finalize_card(raw, _comments(1))
    assert kept == [{"text": "liked it", "count": 2, "comment_ids": ["1", "2"]}]
    assert "2 of 6 liked it." in card


def test_negation_is_respected():
    claims = {c["theme"]: c["comment_ids"] for c in ThemeSummariser().claims(_comments(1))}
    assert "4" not in claims["sweetness"]  # "not too sweet"
    assert "5" in claims["sweetness"]  # "with less sugar"


def test_every_claim_in_card_carries_count():
    card, kept = finalize_card(ThemeSummariser().claims(_comments(2)), _comments(2))
    for c in kept:
        assert f"{c['count']} of 12 {c['text']}." in card
    json.dumps(kept)


def test_claude_backend_output_goes_through_the_same_gate():
    """No API key in CI: a fake client returns what the model might, including bad ids and counts."""
    from types import SimpleNamespace

    from recipe_agent.cook_notes import ClaudeSummariser

    payload = {"claims": [{"text": "made it for a party and everyone loved it", "comment_ids": ["1", "3", "77"]},
                          {"text": "says 9 people loved it", "comment_ids": ["2"]}]}
    calls = []

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(stop_reason="end_turn",
                                   content=[SimpleNamespace(type="text", text=json.dumps(payload))])

    client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    card, kept = finalize_card(ClaudeSummariser(client).claims(_comments(1)), _comments(1))
    assert calls[0]["model"] == "claude-opus-5-5"
    assert calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert kept == [{"text": "made it for a party and everyone loved it", "count": 2, "comment_ids": ["1", "3"]}]
    assert card == "Cook notes (6 comments): 2 of 6 made it for a party and everyone loved it."
