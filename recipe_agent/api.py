"""HTTP backend (deployed on Railway).

    uvicorn recipe_agent.api:app --host 0.0.0.0 --port $PORT

Read endpoints are public. Endpoints that spend Groq tokens or send email need
`Authorization: Bearer $ADMIN_TOKEN`.

Environment
  GROQ_API_KEY      enables the Groq cook-notes summariser (otherwise the deterministic one runs)
  GROQ_MODEL        optional model override
  ADMIN_TOKEN       required for POST endpoints (no token set = POST endpoints disabled)
  DATA_DIR          where records, the dataset, checkpoints and logs live (mount a volume here)
  FETCH_MODE        auto | live | snapshot (default auto: live first, pinned snapshot as fallback)
  N8N_WEBHOOK_URL   n8n production webhook that starts the PDF + approval-email hand-off
  PUBLIC_URL        this service's public https URL, passed to n8n so it can call back
  CORS_ORIGINS      comma-separated origins for the browser frontend (default *)
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, HttpUrl

from .batch import compile_dataset, read_urls, thread_id
from .config import CARD_WORD_CAP, COMMENT_THRESHOLD, DATA_DIR as REPO_DATA_DIR, OUTPUT_DIR, RETRY_CAP
from .cook_notes import get_summariser
from .fetch import PageFetcher
from .graph import build_graph
from .mcp_client import NutritionClient
from .nodes import AgentDeps
from .report import build_pdf, summarize
from .run_log import RunLogger

DATA = Path(os.environ.get("DATA_DIR", str(OUTPUT_DIR)))
RUNS: dict[str, dict] = {}  # run registry for progress polling (in memory; records are on disk)
STATE: dict = {}


def _seed_data_dir() -> None:
    """First start on an empty volume: copy the committed 25-recipe dataset so the UI has data."""
    DATA.mkdir(parents=True, exist_ok=True)
    if DATA.resolve() != OUTPUT_DIR.resolve() and not (DATA / "records").exists() and (OUTPUT_DIR / "records").exists():
        shutil.copytree(OUTPUT_DIR / "records", DATA / "records")
    if not (DATA / "dataset.json").exists():
        compile_dataset(DATA)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_data_dir()
    async with NutritionClient() as nutrition, AsyncSqliteSaver.from_conn_string(str(DATA / "checkpoints.sqlite")) as saver:
        STATE["graph"] = build_graph(saver)
        STATE["deps"] = AgentDeps(
            fetcher=PageFetcher(mode=os.environ.get("FETCH_MODE", "auto")),
            nutrition=nutrition,
            summariser=get_summariser("auto"),
            logger=RunLogger(DATA / "logs" / "run_log.jsonl"),
            output_dir=DATA,
        )
        STATE["lock"] = asyncio.Lock()  # one run at a time: one MCP session, one Groq budget
        yield


app = FastAPI(title="Recipe Research Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def require_admin(authorization: str = Header(default="")) -> None:
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        raise HTTPException(503, "ADMIN_TOKEN is not configured on the server")
    if not hmac.compare_digest(authorization.removeprefix("Bearer ").strip(), token):
        raise HTTPException(401, "missing or wrong admin token")


def _dataset() -> dict:
    return json.loads((DATA / "dataset.json").read_text())


# ------------------------------------------------------------------------------------- read
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {
        "retry_cap": RETRY_CAP,
        "comment_threshold": COMMENT_THRESHOLD,
        "card_word_cap": CARD_WORD_CAP,
        "summariser": STATE["deps"].summariser.name,
        "fetch_mode": STATE["deps"].fetcher.mode,
        "handoff_configured": bool(os.environ.get("N8N_WEBHOOK_URL")),
        "admin_configured": bool(os.environ.get("ADMIN_TOKEN")),
    }


@app.get("/api/summary")
def summary():
    return summarize(_dataset())


@app.get("/api/recipes")
def recipes():
    rows = []
    for r in _dataset()["recipes"]:
        nut = r["nutrition"]
        rows.append({
            "recipe_id": r["recipe_id"], "title": r["title"], "site": r["site"], "source_url": r["source_url"],
            "terminal": r["terminal"], "matched": r["match"]["matched"], "ingredients": r["match"]["ingredients"],
            "nutrition_complete": nut["complete"], "with_nutrition": nut["ingredients_with_nutrition"],
            "energy_kcal": nut["totals"]["energy_kcal"], "card": r["cook_notes"]["status"] == "produced",
            "comment_count": r["cook_notes"]["comment_count"],
        })
    return rows


@app.get("/api/recipes/{recipe_id}")
def recipe(recipe_id: str):
    path = DATA / "records" / f"{recipe_id}.json"
    if not recipe_id.startswith("rcp_") or not path.exists():
        raise HTTPException(404, "unknown recipe id")
    return json.loads(path.read_text())


@app.get("/api/report.pdf")
def report_pdf():
    pdf = build_pdf(_dataset())
    (DATA / "recipe_dataset.pdf").write_bytes(pdf)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="recipe_dataset.pdf"'})


# alias kept for the n8n workflow
app.get("/summary")(summary)
app.get("/report.pdf")(report_pdf)


# ------------------------------------------------------------------------------------ runs
class RunRequest(BaseModel):
    url: HttpUrl


async def _run(run_id: str, url: str, label: str) -> None:
    run = RUNS[run_id]
    graph, deps = STATE["graph"], STATE["deps"]
    cfg = {"configurable": {"thread_id": thread_id(url, label)}}
    async with STATE["lock"]:
        run["status"] = "running"
        try:
            snap = await graph.aget_state(cfg)
            inp = None if snap.next else {"url": url, "node_path": []}
            async for update in graph.astream(inp, cfg, context=deps, stream_mode="updates", durability="sync"):
                for node_name in update:
                    run["node_path"].append(node_name)
            final = (await graph.aget_state(cfg)).values
            run.update(status="done", terminal=final.get("terminal"),
                       recipe_id=(final.get("recipe") or {}).get("recipe_id"))
            compile_dataset(DATA)
        except Exception as e:  # surfaced to the UI; the checkpoint lets a retry resume
            run.update(status="error", error=f"{type(e).__name__}: {e}"[:300])
        finally:
            run["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.post("/api/runs", dependencies=[Depends(require_admin)])
async def start_run(req: RunRequest):
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"run_id": run_id, "url": str(req.url), "status": "queued", "node_path": [],
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    label = "web-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    asyncio.create_task(_run(run_id, str(req.url), label))
    return RUNS[run_id]


@app.get("/api/runs/{run_id}")
def run_status(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run id")
    return RUNS[run_id]


@app.post("/api/batch", dependencies=[Depends(require_admin)])
async def start_batch():
    """Re-run the 25 recipes in data/recipes.txt, then trigger the n8n hand-off if configured."""
    label = "batch-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ids = []
    for url in read_urls(REPO_DATA_DIR / "recipes.txt"):
        run_id = uuid.uuid4().hex[:12]
        RUNS[run_id] = {"run_id": run_id, "url": url, "status": "queued", "node_path": [], "batch": label}
        ids.append(run_id)

    async def go():
        for run_id in ids:
            await _run(run_id, RUNS[run_id]["url"], label)
        if os.environ.get("N8N_WEBHOOK_URL"):
            await _notify_n8n(label)

    asyncio.create_task(go())
    return {"batch": label, "run_ids": ids}


async def _notify_n8n(batch: str) -> dict:
    url = os.environ.get("N8N_WEBHOOK_URL")
    if not url:
        raise HTTPException(503, "N8N_WEBHOOK_URL is not configured on the server")
    public = os.environ.get("PUBLIC_URL") or (
        f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}" if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else "")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, json={"backend_url": public, "batch": batch, "summary": summary()})
    return {"status": r.status_code, "n8n": r.text[:200]}


@app.post("/api/handoff", dependencies=[Depends(require_admin)])
async def handoff():
    """Start the n8n workflow: PDF + drafted email, sent only after a human approves."""
    return await _notify_n8n("manual")
