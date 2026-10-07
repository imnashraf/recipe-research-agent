"""Check 1: every one of the 25 runs ended in a declared terminal state, inside the retry cap,
with its required fields present. Reports the match rate and every unmatched ingredient with the
queries tried.   python evals/check_batch.py
"""

import asyncio
import json
import sys

from _common import OUTPUT_DIR, REPORTS, latest_states, md_table, urls

from recipe_agent.batch import thread_id
from recipe_agent.config import RETRY_CAP
from recipe_agent.state import TERMINAL_STATES

REQUIRED_RECORD = ("recipe_id", "source_url", "title", "provenance", "ingredients", "match", "nutrition",
                   "cook_notes", "terminal", "node_path")
REQUIRED_INGREDIENT = ("raw", "status", "attempts", "queries_tried", "nutrition_status")


def main() -> int:
    states = asyncio.run(latest_states(OUTPUT_DIR / "checkpoints.sqlite"))
    problems, rows = [], []
    all_ings = []
    for url in urls():
        st = states.get(thread_id(url, "batch"))
        if not st:
            problems.append(f"{url}: no run found")
            continue
        term = st.get("terminal", {})
        rec_path = OUTPUT_DIR.parent / st.get("written_to", "missing")
        rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
        missing = [k for k in REQUIRED_RECORD if k not in rec]
        over_cap = [i["raw"] for i in st.get("ingredients", []) if i["attempts"] > RETRY_CAP]
        not_final = [i["raw"] for i in st.get("ingredients", []) if i["status"] not in ("matched", "unknown")]
        bad_ing = [i.get("raw") for i in rec.get("ingredients", []) if any(k not in i for k in REQUIRED_INGREDIENT)]
        ok = term.get("state") in TERMINAL_STATES and term.get("reason") and not (missing or over_cap or not_final or bad_ing)
        if not ok:
            problems.append(f"{url}: state={term} missing={missing} over_cap={over_cap} not_final={not_final}")
        max_attempts = max((i["attempts"] for i in st.get("ingredients", [])), default=0)
        rows.append([rec.get("recipe_id"), rec.get("title"), term.get("state"), rec["match"]["matched"] if rec else "-",
                     rec["match"]["ingredients"] if rec else "-", max_attempts, rec.get("cook_notes", {}).get("status"),
                     "ok" if ok else "FAIL"])
        for i in rec.get("ingredients", []):
            all_ings.append((rec["recipe_id"], i))

    matched = sum(i["status"] == "matched" for _, i in all_ings)
    with_n = sum(i["nutrition_status"] == "computed" for _, i in all_ings)
    unmatched = [(rid, i) for rid, i in all_ings if i["status"] == "unknown"]
    no_grams = [(rid, i) for rid, i in all_ings if i["status"] == "matched" and i["nutrition_status"] != "computed"]
    out = [
        "# Check 1: batch termination, required fields, match rate",
        "",
        f"Runs checked: {len(rows)} of {len(urls())}. Problems: {len(problems)}.",
        f"Retry cap: {RETRY_CAP}. Highest attempt count on any ingredient: "
        f"{max((i['attempts'] for _, i in all_ings), default=0)}.",
        "",
        f"**Match rate: {matched}/{len(all_ings)} = {matched / len(all_ings):.1%}** of ingredient lines matched to a USDA SR28 food id. "
        f"{with_n} of them also have a gram weight, so nutrition covers {with_n / len(all_ings):.1%} of lines. "
        f"{len(unmatched)} unknown; {len(no_grams)} matched but without a gram weight.",
        "",
        md_table(rows, ["recipe id", "title", "terminal state", "matched", "ingredients", "max attempts", "cook notes", "check"]),
        "",
        "## Every unmatched ingredient, with the queries tried",
        "",
        md_table([[rid, i["raw"], i["attempts"], " → ".join(i["queries_tried"]), i["unknown_reason"]] for rid, i in unmatched],
                 ["recipe id", "ingredient line", "attempts", "queries tried", "reason"]),
        "",
        "## Matched to a food id but no gram weight (nutrition left out, not estimated)",
        "",
        md_table([[rid, i["raw"], i["food_id"], i["gram_basis"]] for rid, i in no_grams],
                 ["recipe id", "ingredient line", "food id", "why no grams"]),
    ]
    if problems:
        out += ["", "## Problems", ""] + [f"- {p}" for p in problems]
    (REPORTS / "01_batch_check.md").write_text("\n".join(out) + "\n")
    print("\n".join(out[:8]))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
