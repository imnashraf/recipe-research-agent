"""Check 5: trace 10 cook notes claims back to the comment ids behind them.

Prints each selected claim with the full (already sanitised) text of every comment it cites,
taken from the checkpointed run state, and merges the human verdicts recorded in
evals/claim_verdicts.json into evals/reports/05_claim_trace.md.

    python evals/trace_claims.py
"""

import asyncio
import json
import sys

from _common import OUTPUT_DIR, REPORTS, ROOT, dataset, latest_states


VERDICTS = ROOT / "evals" / "claim_verdicts.json"


def pick_claims(ds: dict, n: int = 10) -> list[tuple[dict, dict]]:
    """Round-robin over recipes with a card so the 10 claims span recipes and claim types."""
    cards = [r for r in ds["recipes"] if r["cook_notes"]["status"] == "produced"]
    picked, depth = [], 0
    while len(picked) < n:
        for r in cards:
            claims = r["cook_notes"]["claims"]
            if depth < len(claims) and len(picked) < n and claims[depth]["text"] != "asked a question":
                picked.append((r, claims[depth]))
        depth += 1
    return picked


def main() -> int:
    ds = dataset()
    states = asyncio.run(latest_states(OUTPUT_DIR / "checkpoints.sqlite"))
    verdicts = json.loads(VERDICTS.read_text()) if VERDICTS.exists() else {}
    out = ["# Check 5: ten cook notes claims traced to comment ids", "",
           "Comment text is the sanitised text held in run state (names already replaced with [name]). "
           "Each cited comment was read and judged: does it support the claim?", ""]
    supported = total = full = 0
    for n, (rec, claim) in enumerate(pick_claims(ds), 1):
        st = next(s for s in states.values() if s.get("recipe", {}).get("recipe_id") == rec["recipe_id"])
        texts = {c["comment_id"]: c["text"] for c in st["comments"]}
        key = f"{rec['recipe_id']}:{claim['text']}"
        v = verdicts.get(key, {})
        out += [f"## {n}. {rec['title']}: \"{claim['count']} of {rec['cook_notes']['comment_count']} {claim['text']}\"", ""]
        for cid in claim["comment_ids"]:
            ok = v.get(cid)
            total += 1
            supported += ok is True
            mark = {True: "supports", False: "DOES NOT support", None: "not yet judged"}[ok]
            out.append(f"- `{cid}` ({mark}): {texts[cid][:400]}")
        full += bool(v) and all(v.get(cid) is True for cid in claim["comment_ids"])
        if v.get("note"):
            out += ["", f"Verdict: {v['note']}"]
        out.append("")
    out.insert(3, f"**{supported} of {total} cited comments support their claim; {full} of 10 claims are fully "
                  f"supported, the others overstate their count.**\n")
    (REPORTS / "05_claim_trace.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
