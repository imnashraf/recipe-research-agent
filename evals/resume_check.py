"""Check 3: interrupt a run, resume from the checkpoint, and confirm the record equals an
uninterrupted run of the same recipe.

Two interruptions:
  1. a real process kill: the batch CLI is started for one recipe and SIGKILLed as soon as the run
     log shows the first nutrition lookup round finished; the same command is then run again.
  2. an in-process crash injected at the start of the 2nd match_nutrition round (inside the retry
     loop), resumed with graph.ainvoke(None, config).

    python evals/resume_check.py
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time

from _common import OUTPUT_DIR, REPORTS, ROOT

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from recipe_agent.cook_notes import ThemeSummariser
from recipe_agent.fetch import PageFetcher
from recipe_agent.graph import build_graph
from recipe_agent.mcp_client import NutritionClient
from recipe_agent.nodes import AgentDeps, InjectedCrash
from recipe_agent.run_log import RunLogger

URL = "https://www.zenbelly.com/gingerbread/"  # 3 lookup rounds, give-up, summarise: the longest path


def cli(out_dir, label="resume"):
    return [sys.executable, "-m", "recipe_agent.batch", "--url", URL, "--label", label, "--output-dir", str(out_dir)]


def record_of(out_dir):
    files = list((out_dir / "records").glob("*.json"))
    return json.loads(files[0].read_text()) if files else None


def kill_and_resume(work):
    base, killed = work / "uninterrupted", work / "killed"
    subprocess.run(cli(base), cwd=ROOT, check=True, capture_output=True)
    log = killed / "logs" / "run_log.jsonl"
    proc = subprocess.Popen(cli(killed), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    deadline = time.time() + 120
    while time.time() < deadline:
        if log.exists() and '"event": "match_round"' in log.read_text():
            os.killpg(proc.pid, signal.SIGKILL)  # kill the agent and its MCP server child
            break
        time.sleep(0.02)
    proc.wait()
    events_before = [json.loads(l) for l in log.read_text().splitlines()]
    assert record_of(killed) is None, "run finished before it could be killed"
    resumed = subprocess.run(cli(killed), cwd=ROOT, check=True, capture_output=True, text=True)
    events_after = [json.loads(l) for l in log.read_text().splitlines()][len(events_before):]
    return record_of(base), record_of(killed), events_before, events_after, resumed.stdout


async def crash_and_resume(work):
    async with NutritionClient() as nutrition, AsyncSqliteSaver.from_conn_string(str(work / "cp.sqlite")) as saver:
        graph = build_graph(saver)

        def deps(**kw):
            return AgentDeps(fetcher=PageFetcher("auto"), nutrition=nutrition, summariser=ThemeSummariser(),
                             logger=RunLogger(work / "log.jsonl"), output_dir=work / "output", **kw)

        base = await graph.ainvoke({"url": URL, "node_path": []}, {"configurable": {"thread_id": "base"}},
                                   context=deps(), durability="sync")
        cfg = {"configurable": {"thread_id": "crash"}}
        d = deps(crash_on={"match_nutrition": 2})
        try:
            await graph.ainvoke({"url": URL, "node_path": []}, cfg, context=d, durability="sync")
            raise AssertionError("crash was not triggered")
        except InjectedCrash:
            pass
        snap = await graph.aget_state(cfg)
        done_before = list(snap.values["node_path"])
        calls_before = len(nutrition.calls)
        resumed = await graph.ainvoke(None, cfg, context=d, durability="sync")
        return base, resumed, done_before, snap.next, len(nutrition.calls) - calls_before


def main() -> int:
    work = OUTPUT_DIR / "eval_runs" / "resume"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)

    base1, resumed1, before, after, stdout = kill_and_resume(work)
    same1 = base1 == resumed1
    starts = [e for e in before if e["event"] == "start"]
    resume_ev = [e for e in after if e["event"] == "resume"]
    rerun_fetch = any(e["event"] == "node_done" and e["node"] == "fetch" for e in after)

    (work / "inproc").mkdir()
    base2, resumed2, done_before, next_nodes, new_calls = asyncio.run(crash_and_resume(work / "inproc"))
    same2 = base2["record"] == resumed2["record"]

    lines = [
        "# Check 3: interrupt, resume from checkpoint, compare with an uninterrupted run",
        "",
        f"Recipe: {URL} (3 lookup rounds, give-up, summarise: the longest path).",
        "",
        "## 1. Process killed with SIGKILL",
        "",
        f"- Started the batch CLI for this recipe; killed the process group as soon as the run log showed the first "
        f"`match_round` event. Nodes completed before the kill: "
        f"`{' → '.join(e['node'] for e in before if e['event'] == 'node_done')}`.",
        f"- No record had been written at kill time. Same command run again: it logged `resume` from "
        f"`{resume_ev[0]['from_nodes'] if resume_ev else 'NOT RESUMED'}` and did {'NOT ' if not rerun_fetch else ''}re-run fetch.",
        f"- Nodes run after resume: `{' → '.join(e['node'] for e in after if e['event'] == 'node_done')}`.",
        f"- Record after resume equals the uninterrupted record: **{same1}** (full JSON equality, {len(json.dumps(base1))} bytes).",
        f"- Node path recorded in the resumed record: `{' → '.join(resumed1['node_path'])}`.",
        "",
        "## 2. Crash injected inside the retry loop (2nd match_nutrition call)",
        "",
        f"- Checkpointed node path at the crash: `{' → '.join(done_before)}`; next node to run: `{list(next_nodes)}`.",
        f"- Resumed with `graph.ainvoke(None, config)`: {new_calls} MCP calls after resume (only the remaining lookup rounds).",
        f"- Record after resume equals the uninterrupted record: **{same2}**.",
        "",
        "The run is resumable because each node returns a state update that the SQLite checkpointer saves "
        "(`durability=\"sync\"`) before the next node starts; the thread id is derived from the URL and run label, so "
        "re-running the same command finds the unfinished thread.",
    ]
    (REPORTS / "03_resume.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if (same1 and same2 and resume_ev and not rerun_fetch and starts) else 1


if __name__ == "__main__":
    sys.exit(main())
