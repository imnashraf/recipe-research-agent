import asyncio
import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from recipe_agent import nodes
from recipe_agent.config import COMMENT_THRESHOLD, RETRY_CAP
from recipe_agent.graph import build_graph
from recipe_agent.nodes import InjectedCrash
from recipe_agent.state import TERMINAL_STATES

from .conftest import DAL_URL, InProcessNutrition


def run(coro):
    return asyncio.run(coro)


class RT:  # minimal stand-in for langgraph Runtime when calling a node directly
    def __init__(self, deps):
        self.context = deps


# ---------------------------------------------------------------- nodes, one at a time
def test_fetch_node_alone(make_deps):
    out = run(nodes.fetch({"url": DAL_URL}, RT(make_deps())))
    assert out["node_path"] == ["fetch"] and out["page_provenance"]["sanitized"]
    assert "Marcus" not in out["raw_page"]


def test_fetch_failure_sets_terminal(make_deps):
    out = run(nodes.fetch({"url": "https://nowhere.invalid/x"}, RT(make_deps())))
    assert out["terminal"]["state"] == "failed_fetch"


def test_parse_nodes_alone(make_deps, dal_html):
    deps = make_deps()
    st = {"url": DAL_URL, **run(nodes.fetch({"url": DAL_URL}, RT(deps)))}
    st.update(run(nodes.parse_recipe(st, RT(deps))))
    assert st["recipe"]["title"] == "Toor Dal Fry" and st["recipe"]["servings"] == 4
    st.update(run(nodes.parse_ingredients(st, RT(deps))))
    assert [i["name"] for i in st["ingredients"]][:2] == ["toor dal", "water"]
    assert st["recipe"]["section_headings"] == ["For the tempering:"]
    assert st["ingredients"][0]["stated_grams"] == 200


def test_routers_read_state_only():
    pend = {"status": "pending", "attempts": 1, "plan_index": 1, "query_plan": [{}, {}]}
    assert nodes.route_after_match({"ingredients": [pend]}) == "retry"
    assert nodes.route_after_match({"ingredients": [{**pend, "attempts": RETRY_CAP, "query_plan": [{}] * 5}]}) == "give_up"
    assert nodes.route_after_match({"ingredients": [{**pend, "plan_index": 2}]}) == "give_up"
    assert nodes.route_after_match({"ingredients": [{"status": "matched"}]}) == "done"
    assert nodes.route_after_comments({"comments": [{}] * COMMENT_THRESHOLD}) == "summarise"
    assert nodes.route_after_comments({"comments": [{}] * (COMMENT_THRESHOLD - 1)}) == "skip"


def test_validate_rejects_estimated_numbers():
    rec = {"recipe_id": "r", "source_url": "u", "title": "t", "nutrition": {"ingredients_with_nutrition": 0, "complete": False, "statement": "Partial"},
           "cook_notes": {"status": "skipped_below_threshold", "comment_count": 0, "threshold": 5},
           "ingredients": [{"index": 0, "status": "unknown", "attempts": 1, "food_id": None, "grams": 100,
                            "nutrients": {"energy_kcal": 1}, "nutrition_status": "no_food_id",
                            "unknown_reason": "x", "queries_tried": ["x"]}]}
    errors = nodes.validate_record(rec, [])
    assert any("nutrients without food id" in e for e in errors)
    assert any("unknown ingredient carries numbers" in e for e in errors)


# ---------------------------------------------------------------- whole graph
def invoke(graph, deps, url, thread="t1"):
    cfg = {"configurable": {"thread_id": thread}}
    return run(graph.ainvoke({"url": url, "node_path": []}, cfg, context=deps))


def test_full_run_toor_dal(make_deps):
    deps = make_deps()
    out = invoke(build_graph(InMemorySaver()), deps, DAL_URL)
    assert out["terminal"]["state"] in TERMINAL_STATES
    dal = out["ingredients"][0]
    assert dal["status"] == "matched" and dal["food_id"] == "16101" and dal["attempts"] == 3
    assert dal["queries_tried"] == ["toor dal", "arhar dal", "Pigeon peas (red gram), mature seeds, raw"]
    assert dal["grams"] == 200
    asafoetida = out["ingredients"][-1]
    assert asafoetida["status"] == "unknown" and asafoetida["grams"] is None and asafoetida["nutrients"] is None
    # 3 cook comments (author reply excluded) < threshold -> skip branch
    assert out["cook_notes"]["status"] == "skipped_below_threshold" and out["cook_notes"]["comment_count"] == 3
    assert out["node_path"] == ["fetch", "parse_recipe", "parse_ingredients", "match_nutrition", "match_nutrition",
                                "match_nutrition", "mark_unknown", "gather_comments", "validate", "write"]
    assert out["terminal"]["state"] == "complete_partial"
    written = json.loads((deps.output_dir / "records" / f"{out['recipe']['recipe_id']}.json").read_text())
    assert written["terminal"] == out["terminal"]


def test_tool_errors_are_retried_within_cap(make_deps):
    nut = InProcessNutrition(fail_first_searches=6)  # first round fails for every ingredient
    out = invoke(build_graph(InMemorySaver()), make_deps(nutrition=nut), DAL_URL)
    salt = next(i for i in out["ingredients"] if i["name"] == "salt")
    assert [a["outcome"] for a in salt["attempt_log"]] == ["tool_error", "matched"]
    assert all(i["attempts"] <= RETRY_CAP for i in out["ingredients"])


def test_fetch_failure_path_ends_in_declared_state(make_deps):
    out = invoke(build_graph(InMemorySaver()), make_deps(), "https://nowhere.invalid/recipe")
    assert out["terminal"]["state"] == "failed_fetch"
    assert out["node_path"][0] == "fetch" and out["node_path"][-2:] == ["validate", "write"]
    assert "parse_recipe:skipped" in out["node_path"]


def test_parse_failure_path(make_deps):
    deps = make_deps(pages={"https://x.example/": "<html><body>No recipe here</body></html>"})
    out = invoke(build_graph(InMemorySaver()), deps, "https://x.example/")
    assert out["terminal"]["state"] == "failed_parse"


@pytest.mark.parametrize("crash_node, call", [("gather_comments", 1), ("match_nutrition", 2), ("write", 1)])
def test_resume_from_checkpoint_matches_uninterrupted(make_deps, crash_node, call):
    baseline = invoke(build_graph(InMemorySaver()), make_deps(), DAL_URL)

    saver = InMemorySaver()
    graph = build_graph(saver)
    nut = InProcessNutrition()
    deps = make_deps(nutrition=nut, crash_on={crash_node: call})
    cfg = {"configurable": {"thread_id": "crashy"}}
    with pytest.raises(InjectedCrash):
        run(graph.ainvoke({"url": DAL_URL, "node_path": []}, cfg, context=deps))
    pending = run(graph.aget_state(cfg)).next
    assert pending == (crash_node,)  # resumes exactly at the node that did not complete
    calls_before = len(nut.calls)
    resumed = run(graph.ainvoke(None, cfg, context=deps))
    assert resumed["record"] == baseline["record"]
    if crash_node != "match_nutrition":
        assert len(nut.calls) == calls_before  # completed lookups are not redone
