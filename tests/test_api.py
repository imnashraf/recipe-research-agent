"""Backend API: read endpoints, admin auth, and one real run through HTTP (snapshot fetch, real MCP)."""

import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    monkeypatch.setenv("FETCH_MODE", "snapshot")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    import recipe_agent.api as api

    api = importlib.reload(api)
    with TestClient(api.app) as c:
        yield c


def test_read_endpoints_serve_the_seeded_dataset(client):
    assert client.get("/health").json() == {"ok": True}
    cfg = client.get("/api/config").json()
    assert (cfg["retry_cap"], cfg["comment_threshold"], cfg["card_word_cap"], cfg["summariser"]) == (3, 5, 60, "themes-v2")
    s = client.get("/api/summary").json()
    assert s["recipes"] == 25 and s["matched"] == 263
    rows = client.get("/api/recipes").json()
    rec = client.get(f"/api/recipes/{rows[0]['recipe_id']}").json()
    assert rec["source_url"] == rows[0]["source_url"]
    assert client.get("/api/recipes/../../etc").status_code == 404
    pdf = client.get("/api/report.pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"


def test_post_endpoints_need_the_admin_token(client):
    url = {"url": "https://www.wyseguide.com/blueberry-cobbler/"}
    assert client.post("/api/runs", json=url).status_code == 401
    assert client.post("/api/runs", json=url, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/handoff", headers={"Authorization": "Bearer s3cret"}).status_code == 503  # no n8n URL


def test_run_one_recipe_over_http(client):
    r = client.post("/api/runs", json={"url": "https://www.wyseguide.com/blueberry-cobbler/"},
                    headers={"Authorization": "Bearer s3cret"})
    run_id = r.json()["run_id"]
    for _ in range(300):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert run["status"] == "done", run
    assert run["terminal"]["state"] == "complete_partial"
    assert run["node_path"][0] == "fetch" and run["node_path"][-1] == "write"
    assert client.get(f"/api/recipes/{run['recipe_id']}").json()["title"] == "Blueberry Cobbler"
