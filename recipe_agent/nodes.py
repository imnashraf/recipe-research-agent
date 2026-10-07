"""Graph nodes. One job each; every input comes from state and every output goes back into it.

Dependencies (page fetcher, nutrition MCP client, summariser, logger) arrive through the LangGraph
runtime context (`AgentDeps`). They are services, not data: nothing a later node reads travels
through them.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from langgraph.runtime import Runtime

from .config import CARD_WORD_CAP, COMMENT_THRESHOLD, NUTRITION_SOURCE, OUTPUT_DIR, RETRY_CAP
from .cook_notes import MIN_SUPPORT, count_words, finalize_card
from .fetch import FetchError, PageFetcher
from .ingredient_parse import normalize_line, parse_ingredient
from .matching import compute_grams, initial_plan, judge, nutrient_contribution
from .pii import find_pii
from .run_log import RunLogger
from .sanitize import sanitize_page
from .state import RecipeState, TerminalState

NUTRIENT_KEYS = (
    "energy_kcal", "protein_g", "fat_g", "saturated_fat_g", "carbohydrate_g", "fiber_g",
    "sugars_g", "sodium_mg", "cholesterol_mg",
)
FAILED = {TerminalState.FAILED_FETCH.value, TerminalState.FAILED_PARSE.value}


@dataclass
class AgentDeps:
    fetcher: PageFetcher
    nutrition: object  # NutritionClient-compatible: async search_foods(), get_food()
    summariser: object  # .claims(comments) -> list[dict], .name
    logger: RunLogger = field(default_factory=lambda: RunLogger(None))
    output_dir: Path = OUTPUT_DIR
    # test hook for the resume check: {node_name: n} raises on the n-th call of that node
    crash_on: dict = field(default_factory=dict)
    calls: dict = field(default_factory=dict)


class InjectedCrash(RuntimeError):
    pass


def node(name: str, runs_after_failure: bool = False):
    """Wrap a node: crash hook, skip after a fetch/parse failure, node_path entry, logging."""

    def deco(fn):
        async def wrapper(state: RecipeState, runtime: Runtime[AgentDeps]):
            deps = runtime.context
            deps.calls[name] = deps.calls.get(name, 0) + 1
            if deps.crash_on.get(name) == deps.calls[name]:
                deps.crash_on.pop(name)
                deps.logger.log("crash_injected", node=name, call=deps.calls[name], url=state.get("url"))
                raise InjectedCrash(f"injected crash in {name} (call {deps.calls[name]})")
            failed = state.get("terminal", {}).get("state") in FAILED
            if failed and not runs_after_failure:
                deps.logger.log("node_skipped", node=name, url=state.get("url"))
                return {"node_path": [f"{name}:skipped"]}
            update = await fn(state, deps)
            deps.logger.log("node_done", node=name, url=state.get("url"),
                            recipe_id=(update.get("recipe") or state.get("recipe") or {}).get("recipe_id"))
            update["node_path"] = [name]
            return update

        wrapper.__name__ = wrapper.__qualname__ = name
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return deco


# ------------------------------------------------------------------------------------- fetch
@node("fetch")
async def fetch(state: RecipeState, deps: AgentDeps) -> dict:
    url = state["url"]
    try:
        page = await asyncio.to_thread(deps.fetcher.fetch, url)
    except FetchError as e:
        return {"terminal": {"state": TerminalState.FAILED_FETCH.value, "reason": str(e)}}
    sanitized, summary = sanitize_page(page.html)
    deps.logger.log("fetched", url=url, source=page.source, recipes=summary["recipes"], comments=summary["comments"])
    return {
        "raw_page": sanitized,
        "page_provenance": {
            "source": page.source,
            "fetched_url": page.fetched_url,
            "original_sha256": page.sha256,
            "sanitized": True,
        },
    }


# ------------------------------------------------------------------------------- parse recipe
def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x).strip() for x in v if str(x).strip()]


def _servings(yields: list[str]) -> tuple[int | None, str | None]:
    """A single whole number of servings, or None. Ranges ('28-32 cookies') stay None."""
    for y in sorted(yields, key=len, reverse=True):
        m = re.match(r"^\s*(\d+)\s*([A-Za-z][A-Za-z\s]*)?(\(.*\))?\s*$", y)
        if m:
            unit = (m.group(2) or "servings").strip().lower()
            n = int(m.group(1))
            if unit == "dozen":
                return n * 12, "pieces"
            return n, unit
    return None, None


@node("parse_recipe")
async def parse_recipe(state: RecipeState, deps: AgentDeps) -> dict:
    soup = BeautifulSoup(state["raw_page"], "lxml")
    recipes = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            recipes.append(json.loads(script.string))
        except (TypeError, json.JSONDecodeError):
            continue
    recipes = [r for r in recipes if r.get("recipeIngredient")]
    if not recipes:
        return {"terminal": {"state": TerminalState.FAILED_PARSE.value, "reason": "no schema.org Recipe with ingredients on page"}}
    r = recipes[0]
    canonical = soup.find("link", rel="canonical")
    source_url = canonical["href"] if canonical else state["url"]
    yields = _as_list(r.get("recipeYield")) if not isinstance(r.get("recipeYield"), (int, float)) else [str(r["recipeYield"])]
    servings, unit = _servings(yields)
    lines = [normalize_line(x) for x in r["recipeIngredient"] if str(x).strip()]
    return {
        "recipe": {
            "recipe_id": "rcp_" + hashlib.sha1(source_url.encode()).hexdigest()[:10],
            "source_url": source_url,
            "title": normalize_line(str(r.get("name", ""))),
            "site": urlparse(source_url).netloc.removeprefix("www."),
            "category": _as_list(r.get("recipeCategory")),
            "cuisine": _as_list(r.get("recipeCuisine")),
            "yield_text": " / ".join(yields) or None,
            "servings": servings,
            "servings_unit": unit,
            "ingredient_lines": lines,
            "section_headings": [],
        }
    }


# --------------------------------------------------------------------------- parse ingredients
@node("parse_ingredients")
async def parse_ingredients(state: RecipeState, deps: AgentDeps) -> dict:
    recipe = dict(state["recipe"])
    ingredients, headings = [], []
    for line in recipe["ingredient_lines"]:
        p = parse_ingredient(line)
        if p.is_heading:
            headings.append(p.raw)
            continue
        ingredients.append(
            {
                "index": len(ingredients),
                "raw": p.raw,
                "name": p.name,
                "quantity": round(p.quantity, 4) if p.quantity is not None else None,
                "unit": p.unit,
                "size_word": p.size_word,
                "stated_grams": round(p.stated_grams, 2) if p.stated_grams else None,
                "status": "pending",
                "query_plan": initial_plan(p.name) if p.name else [],
                "plan_index": 0,
                "attempts": 0,
                "queries_tried": [],
                "attempt_log": [],
                "food_id": None,
                "food_description": None,
                "grams": None,
                "gram_basis": None,
                "nutrition_status": "no_food_id",
                "nutrients": None,
                "unknown_reason": None,
            }
        )
    recipe["section_headings"] = headings
    if not ingredients:
        return {"recipe": recipe, "terminal": {"state": TerminalState.FAILED_PARSE.value, "reason": "no ingredient lines parsed"}}
    return {"recipe": recipe, "ingredients": ingredients, "retry_round": 0}


# ----------------------------------------------------------------------------- match nutrition
def can_retry(ing: dict) -> bool:
    return ing["status"] == "pending" and ing["attempts"] < RETRY_CAP and ing["plan_index"] < len(ing["query_plan"])


def aggregate_nutrition(ingredients: list[dict], servings: int | None) -> dict:
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    missing_nutrient_values: dict[str, int] = {}
    with_nutrition = [i for i in ingredients if i.get("nutrition_status") == "computed"]
    for ing in with_nutrition:
        for k in NUTRIENT_KEYS:
            v = ing["nutrients"].get(k)
            if v is None:
                missing_nutrient_values[k] = missing_nutrient_values.get(k, 0) + 1
            else:
                totals[k] += v
    unknown_food = sum(1 for i in ingredients if i.get("status") != "matched")
    no_grams = sum(1 for i in ingredients if i.get("status") == "matched" and i.get("nutrition_status") != "computed")
    n, k = len(ingredients), len(with_nutrition)
    complete = k == n
    statement = (
        f"Complete: all {n} ingredients have nutrition from a USDA food id."
        if complete
        else f"Partial: {n - k} of {n} ingredients have no nutrition ({unknown_food} unmatched food, "
        f"{no_grams} matched but no gram weight); totals cover the other {k} only."
    )
    totals = {key: round(v, 1) for key, v in totals.items()}
    return {
        "basis": "whole recipe, sum of ingredients with a food id and a gram weight",
        "source": NUTRITION_SOURCE,
        "complete": complete,
        "ingredients_total": n,
        "ingredients_with_nutrition": k,
        "unmatched_food_count": unknown_food,
        "matched_without_grams_count": no_grams,
        "statement": statement,
        "totals": totals,
        "per_serving": (
            {key: round(v / servings, 1) for key, v in totals.items()} if servings else None
        ),
        "servings": servings,
        "nutrient_values_missing_in_usda": missing_nutrient_values,
    }


@node("match_nutrition")
async def match_nutrition(state: RecipeState, deps: AgentDeps) -> dict:
    ingredients = copy.deepcopy(state["ingredients"])
    rnd = state.get("retry_round", 0) + 1
    for ing in ingredients:
        if not can_retry(ing):
            continue
        step = ing["query_plan"][ing["plan_index"]]
        ing["attempts"] += 1
        entry = {"attempt": ing["attempts"], "query": step["query"], "strategy": step["strategy"]}
        try:
            candidates = await deps.nutrition.search_foods(step["query"], 10)
        except Exception as e:  # tool failure: count the attempt, retry the same query next round
            ing["attempt_log"].append({**entry, "outcome": "tool_error", "detail": type(e).__name__})
            ing["queries_tried"].append(step["query"])
            continue
        ing["queries_tried"].append(step["query"])
        hit, why = judge(candidates, step["strategy"], step["query"])
        if hit is None:
            ing["plan_index"] += 1
            outcome = "no_candidates" if why == "no_candidates" else "rejected"
            ing["attempt_log"].append({**entry, "outcome": outcome, "detail": why})
            continue
        try:
            food = await deps.nutrition.get_food(hit["food_id"])
        except Exception as e:
            ing["attempt_log"].append({**entry, "outcome": "tool_error", "detail": f"get_food {type(e).__name__}"})
            continue
        ing["attempt_log"].append({**entry, "outcome": "matched", "detail": f"{food['food_id']} {food['description']}"})
        ing["status"] = "matched"
        ing["food_id"] = food["food_id"]
        ing["food_description"] = food["description"]
        grams, basis = compute_grams(ing, food["portions"], step.get("volume_portions", True))
        ing["gram_basis"] = basis
        if grams is None:
            ing["nutrition_status"] = "no_gram_weight"
        else:
            ing["grams"] = round(grams, 2)
            ing["nutrition_status"] = "computed"
            ing["nutrients"] = nutrient_contribution(food["nutrients_per_100g"], grams)
    deps.logger.log(
        "match_round", url=state["url"], round=rnd,
        matched=sum(i["status"] == "matched" for i in ingredients),
        pending=sum(i["status"] == "pending" for i in ingredients),
    )
    return {
        "ingredients": ingredients,
        "retry_round": rnd,
        "nutrition": aggregate_nutrition(ingredients, state["recipe"].get("servings")),
    }


def route_after_match(state: RecipeState) -> str:
    """Conditional edge 1: retry the lookups that failed, give up on them, or move on."""
    ingredients = state.get("ingredients") or []
    pending = [i for i in ingredients if i["status"] == "pending"]
    if not pending:
        return "done"
    if any(can_retry(i) for i in pending):
        return "retry"
    return "give_up"


@node("mark_unknown")
async def mark_unknown(state: RecipeState, deps: AgentDeps) -> dict:
    ingredients = copy.deepcopy(state["ingredients"])
    for ing in ingredients:
        if ing["status"] != "pending":
            continue
        ing["status"] = "unknown"
        ing["nutrition_status"] = "no_food_id"
        last = ing["attempt_log"][-1]["detail"] if ing["attempt_log"] else "no name to search"
        if ing["attempts"] >= RETRY_CAP:
            ing["unknown_reason"] = f"no acceptable match within the {RETRY_CAP}-attempt cap; last: {last}"
        else:
            ing["unknown_reason"] = f"no other names to try after {ing['attempts']} attempt(s); last: {last}"
    return {"ingredients": ingredients, "nutrition": aggregate_nutrition(ingredients, state["recipe"].get("servings"))}


# --------------------------------------------------------------------------- gather comments
@node("gather_comments")
async def gather_comments(state: RecipeState, deps: AgentDeps) -> dict:
    soup = BeautifulSoup(state["raw_page"], "lxml")
    comments = []
    for li in soup.select("ol.comments li[data-comment-id]"):
        if li.get("data-post-author") == "1" or li.get("data-reply") == "1":
            # only top-level comments are cook reports: nested replies are mostly the recipe author
            # answering, and many sites do not mark the author's replies
            continue
        text = li.get_text(" ", strip=True)
        if text:
            comments.append({"comment_id": li["data-comment-id"], "text": text})
    notes = {
        "status": "skipped_below_threshold",
        "comment_count": len(comments),
        "threshold": COMMENT_THRESHOLD,
        "claims": [],
        "card": None,
        "word_count": 0,
        "backend": None,
    }
    return {"comments": comments, "cook_notes": notes}


def route_after_comments(state: RecipeState) -> str:
    """Conditional edge 2: summarise only when enough cooks commented."""
    return "summarise" if len(state.get("comments") or []) >= COMMENT_THRESHOLD else "skip"


@node("summarise")
async def summarise(state: RecipeState, deps: AgentDeps) -> dict:
    comments = state["comments"]
    raw_claims = await asyncio.to_thread(deps.summariser.claims, comments)
    card, claims = finalize_card(raw_claims, comments, CARD_WORD_CAP)
    return {
        "cook_notes": {
            "status": "produced",
            "comment_count": len(comments),
            "threshold": COMMENT_THRESHOLD,
            "claims": claims,
            "card": card,
            "word_count": count_words(card),
            "backend": deps.summariser.name,
        }
    }


# ------------------------------------------------------------------------------- validate
INGREDIENT_FIELDS = (
    "index", "raw", "name", "quantity", "unit", "status", "food_id", "food_description", "grams",
    "gram_basis", "nutrition_status", "nutrients", "attempts", "queries_tried", "attempt_log", "unknown_reason",
)


def build_record(state: RecipeState) -> dict:
    ingredients = state.get("ingredients") or []
    matched = sum(i["status"] == "matched" for i in ingredients)
    return {
        **{k: state["recipe"][k] for k in (
            "recipe_id", "source_url", "title", "site", "category", "cuisine", "yield_text", "servings", "servings_unit",
        )},
        "provenance": {
            "page_source": state["page_provenance"]["source"],
            "fetched_url": state["page_provenance"]["fetched_url"],
            "original_page_sha256": state["page_provenance"]["original_sha256"],
            "nutrition_source": NUTRITION_SOURCE,
        },
        "section_headings": state["recipe"].get("section_headings", []),
        "ingredients": [{k: i.get(k) for k in INGREDIENT_FIELDS} for i in ingredients],
        "match": {
            "ingredients": len(ingredients),
            "matched": matched,
            "unknown": len(ingredients) - matched,
            "match_rate": round(matched / len(ingredients), 3) if ingredients else 0.0,
            "retry_rounds": state.get("retry_round", 0),
            "hit_retry_cap": sum(1 for i in ingredients if i["status"] == "unknown" and i["attempts"] >= RETRY_CAP),
        },
        "nutrition": state.get("nutrition"),
        "cook_notes": state.get("cook_notes"),
        "node_path": [p for p in state.get("node_path", [])] + ["validate"],
    }


def validate_record(record: dict, comments: list[dict]) -> list[str]:
    errors = []
    for key in ("recipe_id", "source_url", "title", "ingredients", "nutrition", "cook_notes"):
        if not record.get(key):
            errors.append(f"missing {key}")
    for ing in record.get("ingredients", []):
        tag = f"ingredient {ing['index']}"
        if ing["status"] not in ("matched", "unknown"):
            errors.append(f"{tag}: non-final status {ing['status']}")
        if ing["attempts"] > RETRY_CAP:
            errors.append(f"{tag}: {ing['attempts']} attempts exceeds cap {RETRY_CAP}")
        if ing["status"] == "matched" and not ing["food_id"]:
            errors.append(f"{tag}: matched without food id")
        if ing["nutrients"] is not None and (not ing["food_id"] or ing["grams"] is None):
            errors.append(f"{tag}: nutrients without food id and grams")
        if ing["status"] == "unknown" and (ing["nutrients"] is not None or ing["grams"] is not None):
            errors.append(f"{tag}: unknown ingredient carries numbers")
        if ing["status"] == "unknown" and not (ing["unknown_reason"] and ing["queries_tried"]):
            errors.append(f"{tag}: unknown without reason or queries tried")
    nut = record.get("nutrition") or {}
    with_n = sum(1 for i in record["ingredients"] if i["nutrition_status"] == "computed")
    if nut.get("ingredients_with_nutrition") != with_n:
        errors.append("nutrition count does not match ingredients")
    if not nut.get("complete") and "Partial" not in nut.get("statement", ""):
        errors.append("partial nutrition not stated")
    notes = record.get("cook_notes") or {}
    if notes.get("status") == "produced":
        valid_ids = {c["comment_id"] for c in comments}
        if count_words(notes["card"]) > CARD_WORD_CAP:
            errors.append("card over word cap")
        for claim in notes["claims"]:
            if claim["count"] != len(claim["comment_ids"]) or claim["count"] < MIN_SUPPORT:
                errors.append(f"claim '{claim['text']}' count does not match its comment ids")
            if not set(claim["comment_ids"]) <= valid_ids:
                errors.append(f"claim '{claim['text']}' cites unknown comment ids")
            if f"{claim['count']} of" not in notes["card"]:
                errors.append(f"claim '{claim['text']}' has no count in card")
    elif notes.get("comment_count", 0) >= notes.get("threshold", COMMENT_THRESHOLD):
        errors.append("above threshold but no card")
    hits = [h for h in find_pii(json.dumps(record, ensure_ascii=False)) if h[0] != "gazetteer_name"]
    if hits:
        errors.append(f"possible PII in record: {sorted({k for k, _ in hits})}")
    return errors


@node("validate", runs_after_failure=True)
async def validate(state: RecipeState, deps: AgentDeps) -> dict:
    if state.get("terminal", {}).get("state") in FAILED:
        return {"validation": {"ok": False, "errors": [state["terminal"]["reason"]]}}
    record = build_record(state)
    errors = validate_record(record, state.get("comments") or [])
    if errors:
        terminal = {"state": TerminalState.FAILED_VALIDATION.value, "reason": "; ".join(errors)[:500]}
    else:
        m, nut = record["match"], record["nutrition"]
        card = record["cook_notes"]
        card_note = (
            f"card from {card['comment_count']} comments" if card["status"] == "produced"
            else f"no card ({card['comment_count']} comments < threshold {card['threshold']})"
        )
        if nut["complete"]:
            terminal = {"state": TerminalState.COMPLETE.value,
                        "reason": f"all {m['ingredients']} ingredients matched with grams; {card_note}"}
        else:
            terminal = {"state": TerminalState.COMPLETE_PARTIAL.value,
                        "reason": f"{nut['ingredients_total'] - nut['ingredients_with_nutrition']} of {nut['ingredients_total']} "
                                  f"ingredients without nutrition ({m['unknown']} unknown, {m['hit_retry_cap']} hit the "
                                  f"{RETRY_CAP}-attempt cap, {nut['matched_without_grams_count']} no gram weight); {card_note}"}
    record["terminal"] = terminal
    return {"record": record, "validation": {"ok": not errors, "errors": errors}, "terminal": terminal}


# ---------------------------------------------------------------------------------- write
@node("write", runs_after_failure=True)
async def write(state: RecipeState, deps: AgentDeps) -> dict:
    terminal = state["terminal"]
    if terminal["state"] in (TerminalState.COMPLETE.value, TerminalState.COMPLETE_PARTIAL.value):
        record = dict(state["record"])
        record["node_path"] = record["node_path"] + ["write"]
        path = deps.output_dir / "records" / f"{record['recipe_id']}.json"
    else:
        rid = (state.get("recipe") or {}).get("recipe_id") or "url_" + hashlib.sha1(state["url"].encode()).hexdigest()[:10]
        record = {"recipe_id": rid, "source_url": state["url"], "terminal": terminal,
                  "validation": state.get("validation"),
                  "node_path": list(state.get("node_path", [])) + ["write"]}
        path = deps.output_dir / "failures" / f"{rid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    deps.logger.log("terminal", url=state["url"], recipe_id=record["recipe_id"], state=terminal["state"],
                    reason=terminal["reason"], node_path=record["node_path"])
    return {"written_to": str(path.relative_to(deps.output_dir.parent)) if deps.output_dir.parent in path.parents else str(path)}
