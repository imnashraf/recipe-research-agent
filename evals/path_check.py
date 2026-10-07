"""Check 2: one recipe per path through the graph. Each is run fresh (own checkpoint DB) and its
node path compared with the path predicted beforehand from what we know about the page.

    python evals/path_check.py
"""

import asyncio
import json
import shutil
import sys

from _common import OUTPUT_DIR, REPORTS, md_table

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from recipe_agent.cook_notes import ThemeSummariser
from recipe_agent.fetch import PageFetcher
from recipe_agent.graph import build_graph
from recipe_agent.mcp_client import NutritionClient
from recipe_agent.nodes import AgentDeps
from recipe_agent.run_log import RunLogger

HEAD = ["fetch", "parse_recipe", "parse_ingredients"]
TAIL = ["validate", "write"]

# Predictions are written from the inputs alone (ingredient wording, alias table, comment count),
# before looking at the run.
CASES = [
    {
        "path": "A. retry, all matched, summarise",
        "url": "https://www.savorynothings.com/chewy-chocolate-crinkle-cookies/",
        "why": "'all-purpose flour', 'baking powder', 'white sugar' and 'vanilla' miss on their own wording and each "
               "has an alias that hits in round 2; nothing is left unknown; 16 cook comments (>= 5).",
        "expected": HEAD + ["match_nutrition", "match_nutrition", "gather_comments", "summarise"] + TAIL,
        "terminal": "complete",
    },
    {
        "path": "B. retry, hit cap, give up, summarise",
        "url": "https://www.zenbelly.com/gingerbread/",
        "why": "'coconut sugar' and 'tapioca starch' each have two aliases that are not in SR28, so they use all 3 "
               "attempts and are marked unknown; 19 cook comments.",
        "expected": HEAD + ["match_nutrition"] * 3 + ["mark_unknown", "gather_comments", "summarise"] + TAIL,
        "terminal": "complete_partial",
    },
    {
        "path": "C. retry, hit cap, give up, skip card",
        "url": "https://www.asweetpeachef.com/healthy-apple-crumble/",
        "why": "'coconut sugar' exhausts the cap; 'sea salt' has no alias; 4 cook comments (< 5) so no card.",
        "expected": HEAD + ["match_nutrition"] * 3 + ["mark_unknown", "gather_comments"] + TAIL,
        "terminal": "complete_partial",
    },
    {
        "path": "D. retry, give up below cap (no alias), skip card",
        "url": "https://www.garlicandzest.com/easy-banana-cake-recipe/",
        "why": "'all purpose flour', 'baking powder', 'cinnamon' and 'greek yogurt' miss in round 1; the first three have an "
               "alias that hits in round 2; greek yogurt has none (fat level not stated), so it is given up after 1 "
               "attempt without reaching the cap; 1 comment.",
        "expected": HEAD + ["match_nutrition", "match_nutrition", "mark_unknown", "gather_comments"] + TAIL,
        "terminal": "complete_partial",
    },
    {
        "path": "E. fetch fails (live blocked, no snapshot)",
        "url": "https://www.example-recipes.invalid/no-such-recipe/",
        "why": "host does not resolve and the URL has no pinned snapshot; the run must still end in a declared state.",
        "expected": ["fetch", "parse_recipe:skipped", "parse_ingredients:skipped", "match_nutrition:skipped",
                     "gather_comments:skipped", "validate", "write"],
        "terminal": "failed_fetch",
    },
]


async def run_cases(work):
    results = []
    async with NutritionClient() as nutrition, AsyncSqliteSaver.from_conn_string(str(work / "cp.sqlite")) as saver:
        graph = build_graph(saver)
        deps = AgentDeps(fetcher=PageFetcher("auto"), nutrition=nutrition, summariser=ThemeSummariser(),
                         logger=RunLogger(work / "log.jsonl"), output_dir=work / "output")
        for i, case in enumerate(CASES):
            cfg = {"configurable": {"thread_id": f"path-{i}"}}
            out = await graph.ainvoke({"url": case["url"], "node_path": []}, cfg, context=deps, durability="sync")
            results.append(out)
    return results


def main() -> int:
    work = OUTPUT_DIR / "eval_runs" / "paths"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    results = asyncio.run(run_cases(work))
    rows, failures, detail = [], 0, []
    for case, out in zip(CASES, results):
        path = out["node_path"]
        ok = path == case["expected"] and out["terminal"]["state"] == case["terminal"]
        failures += not ok
        rows.append([case["path"], case["url"].split("/")[2], out["terminal"]["state"], "yes" if ok else "NO"])
        detail += [f"### {case['path']}", "", f"- URL: {case['url']}", f"- Expected because: {case['why']}",
                   f"- Expected path: `{' → '.join(case['expected'])}`", f"- Logged path:   `{' → '.join(path)}`",
                   f"- Terminal: `{out['terminal']['state']}`: {out['terminal']['reason']}", ""]
        if out.get("ingredients"):
            retried = [f"{i['raw']} ({' → '.join(i['queries_tried'])}: {i['status']})"
                       for i in out["ingredients"] if i["attempts"] > 1 or i["status"] == "unknown"]
            detail += ["- Ingredients that drove the path: " + "; ".join(retried), ""]
    text = ["# Check 2: one recipe per path through the graph", "",
            "Each recipe was run fresh (its own checkpoint database) against the real MCP nutrition server.", "",
            md_table(rows, ["path", "site", "terminal", "went where expected"]), ""] + detail
    (REPORTS / "02_paths.md").write_text("\n".join(text) + "\n")
    print("\n".join(text[:12]))
    for case, out in zip(CASES, results):
        print(case["path"], json.dumps(out["node_path"]))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
