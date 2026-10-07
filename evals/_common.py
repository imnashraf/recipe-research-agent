from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from recipe_agent.config import DATA_DIR, OUTPUT_DIR  # noqa: E402

REPORTS = ROOT / "evals" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


def urls() -> list[str]:
    return [l.strip() for l in (DATA_DIR / "recipes.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]


def dataset(output_dir: Path = OUTPUT_DIR) -> dict:
    return json.loads((output_dir / "dataset.json").read_text())


def thread_ids(db_path: Path) -> list[str]:
    con = sqlite3.connect(db_path)
    try:
        return [r[0] for r in con.execute("select distinct thread_id from checkpoints order by thread_id")]
    finally:
        con.close()


async def latest_states(db_path: Path) -> dict[str, dict]:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from recipe_agent.graph import build_graph

    out = {}
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_graph(saver)
        for tid in thread_ids(db_path):
            snap = await graph.aget_state({"configurable": {"thread_id": tid}})
            out[tid] = snap.values
    return out


def md_table(rows: list[list], header: list[str]) -> str:
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)
