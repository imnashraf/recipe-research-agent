"""Run the agent over a URL list and compile the dataset.

    python -m recipe_agent.batch                      # 25 recipes in data/recipes.txt
    python -m recipe_agent.batch --url <recipe url>   # one recipe
    python -m recipe_agent.batch --fetch-mode live    # never use snapshots

Each recipe is one LangGraph thread checkpointed in output/checkpoints.sqlite (thread id =
recipe URL hash + run label), so an interrupted run resumes from its last completed node when
the same command is run again.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .config import COMMENT_THRESHOLD, CARD_WORD_CAP, DATA_DIR, OUTPUT_DIR, RETRY_CAP
from .cook_notes import get_summariser
from .fetch import PageFetcher
from .graph import build_graph
from .mcp_client import NutritionClient
from .nodes import AgentDeps
from .run_log import RunLogger


def thread_id(url: str, label: str) -> str:
    return f"{label}:{hashlib.sha1(url.encode()).hexdigest()[:12]}"


def read_urls(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")]


async def run_one(graph, deps: AgentDeps, url: str, label: str) -> dict:
    config = {"configurable": {"thread_id": thread_id(url, label)}}
    snapshot = await graph.aget_state(config)
    if snapshot.values and not snapshot.next:
        return snapshot.values  # finished earlier under this label
    if snapshot.next:
        deps.logger.log("resume", url=url, from_nodes=list(snapshot.next))
        return await graph.ainvoke(None, config, context=deps, durability="sync")
    deps.logger.log("start", url=url, thread=config["configurable"]["thread_id"])
    return await graph.ainvoke({"url": url, "node_path": []}, config, context=deps, durability="sync")


def compile_dataset(output_dir: Path) -> dict:
    """Rebuild dataset.json/.jsonl from every record in output_dir/records.

    The 25 batch recipes come first in data/recipes.txt order; records from other runs (for
    example URLs submitted in the web UI) follow, sorted by title.
    """
    order = {u: i for i, u in enumerate(read_urls(DATA_DIR / "recipes.txt"))}
    records = [json.loads(p.read_text()) for p in sorted((output_dir / "records").glob("*.json"))]
    records.sort(key=lambda r: (order.get(r["source_url"], len(order)), r["title"]))
    dataset = {
        "category": "Dessert",
        "retry_cap": RETRY_CAP,
        "comment_threshold": COMMENT_THRESHOLD,
        "card_word_cap": CARD_WORD_CAP,
        "recipes": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dataset.json").write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n")
    with open(output_dir / "dataset.jsonl", "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return dataset


async def main_async(args) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    urls = [args.url] if args.url else read_urls(Path(args.urls))
    logger = RunLogger(output_dir / "logs" / "run_log.jsonl")
    async with NutritionClient() as nutrition, AsyncSqliteSaver.from_conn_string(
        str(output_dir / "checkpoints.sqlite")
    ) as saver:
        graph = build_graph(saver)
        deps = AgentDeps(
            fetcher=PageFetcher(mode=args.fetch_mode),
            nutrition=nutrition,
            summariser=get_summariser(args.summariser),
            logger=logger,
            output_dir=output_dir,
        )
        results = []
        for i, url in enumerate(urls, 1):
            res = await run_one(graph, deps, url, args.label)
            t = res.get("terminal", {})
            print(f"[{i:2}/{len(urls)}] {t.get('state', '?'):17} {url}\n        {t.get('reason', '')}")
            results.append(res)
    if not args.url:
        ds = compile_dataset(output_dir)
        print(f"dataset: {len(ds['recipes'])} records -> {output_dir / 'dataset.json'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", default=str(DATA_DIR / "recipes.txt"))
    ap.add_argument("--url")
    ap.add_argument("--label", default="batch", help="run label; part of the checkpoint thread id")
    ap.add_argument("--fetch-mode", default="auto", choices=["auto", "live", "snapshot"])
    ap.add_argument("--summariser", default="auto", choices=["auto", "themes", "groq"],
                    help="auto = groq when GROQ_API_KEY is set, else themes")
    ap.add_argument("--output-dir", default=str(OUTPUT_DIR))
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
