"""Pure decision logic for nutrition matching: which query to try next, whether a search result is
an acceptable match, and how many grams an ingredient weighs according to the recipe or the
matched food's USDA portion weights. No I/O here; the match node calls the MCP tools.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from .config import DATA_DIR
from .ingredient_parse import MASS_TO_G, VOLUME_TO_TSP

ACCEPT_MAX_COST = 1.0  # search ranking cost above which the top hit is "not this food"
TIE_MARGIN = 0.05  # two different foods this close at the top = ambiguous, try another name

# Words that change what the food is. If present, never fall back to the bare head noun
# ("vegan butter" must not become "butter").
BLOCKING_MODIFIERS = {
    "vegan", "dairy-free", "plant-based", "gluten-free", "sugar-free", "keto", "low-carb",
    "alternative", "substitute", "imitation", "boxed", "mix", "kosher", "sea", "pink", "coconut",
    "almond", "oat", "soy", "cashew", "recipe", "frosting", "sweetener", "blend", "cake",
}
# Descriptive words that may be dropped for the head-noun fallback.
SAFE_TO_DROP = {
    "creamy", "natural", "granny", "smith", "fuji", "gala", "honeycrisp", "blanched",
    "semi-sweet", "semisweet", "toasted", "large", "small", "medium", "organic",
}


@lru_cache(maxsize=1)
def curated_aliases() -> dict[str, list[str]]:
    data = json.loads((DATA_DIR / "aliases.json").read_text())
    return {k.lower(): v for k, v in data["aliases"].items()}


def head_noun_query(name: str) -> str | None:
    words = name.lower().split()
    if len(words) < 2:
        return None
    if any(w in BLOCKING_MODIFIERS for w in words):
        return None
    if all(w in SAFE_TO_DROP for w in words[:-1]):
        return words[-1]
    return None


def initial_plan(name: str) -> list[dict]:
    """Ordered queries for one ingredient. The first is always the recipe's own wording.

    An alias may carry "volume_portions": false when the alias food is nutritionally the same
    but physically different (almond flour vs whole blanched almonds): its USDA cup/spoon
    weights must not be used, only a mass stated in the recipe.
    """
    plan = [{"query": name, "strategy": "name"}]
    for alias in curated_aliases().get(name.lower(), []):
        if isinstance(alias, dict):
            plan.append({"query": alias["query"], "strategy": "alias",
                         "volume_portions": alias.get("volume_portions", True)})
        else:
            plan.append({"query": alias, "strategy": "alias"})
    head = head_noun_query(name)
    if head:
        plan.append({"query": head, "strategy": "head_noun"})
    seen, out = set(), []
    for step in plan:
        key = step["query"].lower()
        if key not in seen:
            seen.add(key)
            out.append(step)
    return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", text.lower()).strip()


def judge(candidates: list[dict], strategy: str, query: str = "") -> tuple[dict | None, str]:
    """Accept the top search candidate or explain why not."""
    if not candidates:
        return None, "no_candidates"
    if strategy != "name":
        # an alias written as the exact USDA description names that food unambiguously
        for c in candidates:
            if _norm(c["description"]) == _norm(query):
                return c, "matched"
    top = candidates[0]
    max_cost = ACCEPT_MAX_COST
    if top["cost"] > max_cost:
        return None, f"rejected: best hit '{top['description']}' is not a close match (cost {top['cost']} > {max_cost})"
    if len(candidates) > 1 and candidates[1]["cost"] - top["cost"] < TIE_MARGIN:
        return None, (
            f"rejected: ambiguous between '{top['description']}' and '{candidates[1]['description']}'"
        )
    return top, "matched"


# ---------------------------------------------------------------------------------------------
# gram weights

NEUTRAL_QUALIFIERS = {"", "fluid", "unsifted", "unpacked", "not packed", "8 fl oz", "whole"}
PORTION_UNIT_WORDS = {
    "cup": "cup", "cups": "cup", "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "fl oz": "fl oz", "pint": "pint",
    "quart": "quart",
}
INEXACT_MEASURES = ("heaping", "heaped", "scant", "rounded")


def _portion_parts(unit_desc: str) -> tuple[str, str]:
    """'cup, packed' -> ('cup', 'packed'); 'fl oz' -> ('fl oz', ''); 'large' -> ('large', '')."""
    desc = re.sub(r"\s+", " ", unit_desc.lower()).strip()
    head, _, qual = desc.partition(",")
    head, qual = head.strip(), qual.strip()
    qual = re.sub(r"[()]", "", qual).strip()
    if head.startswith("fl oz"):
        return "fl oz", qual
    first = head.split(" ")[0]
    rest = head[len(first):].strip()
    qual = ", ".join(x for x in (rest, qual) if x)
    return first, qual


def _volume_portion(p: dict) -> tuple[float, str] | None:
    """Volume of a USDA portion in teaspoons plus its qualifier, or None if not a volume.

    Handles plain volumes ("1 cup, packed") and servings that state their volume
    ("1 serving, 1/2 cup").
    """
    unit, qual = _portion_parts(p["unit_desc"])
    if unit == "serving":
        m = re.match(r"^(\d+(?:/\d+)?|\d*\.\d+)\s*(cup|tbsp|tsp|tablespoon|teaspoon)\b", qual)
        if not m:
            return None
        n = m.group(1)
        amount = float(n.split("/")[0]) / float(n.split("/")[1]) if "/" in n else float(n)
        return p["amount"] * amount * VOLUME_TO_TSP[PORTION_UNIT_WORDS[m.group(2)]], ""
    unit = PORTION_UNIT_WORDS.get(unit)
    if unit not in VOLUME_TO_TSP:
        return None
    return p["amount"] * VOLUME_TO_TSP[unit], qual


def _qualifier_ok(qual: str, raw_text: str) -> bool:
    qual = re.sub(r"\(.*?\)", "", qual).strip()
    if qual in NEUTRAL_QUALIFIERS or qual.startswith("fluid"):
        return True
    words = [w for w in re.findall(r"[a-z]+", qual) if w not in {"and", "or", "yields", "cups"}]
    raw_words = set(re.findall(r"[a-z]+", raw_text.lower()))
    return bool(words) and all(w in raw_words for w in words)


def _describe(p: dict) -> str:
    return f"USDA portion '{p['amount']:g} {p['unit_desc']}' = {p['grams']:g} g ({p['source_field']})"


def compute_grams(ing: dict, portions: list[dict], volume_portions: bool = True) -> tuple[float | None, str]:
    """Grams for an ingredient, or None with the reason. Never estimates."""
    if ing.get("stated_grams"):
        return ing["stated_grams"], "mass stated in recipe line"
    qty, unit = ing.get("quantity"), ing.get("unit")
    raw = ing.get("raw", "")
    if qty is None:
        return None, "no single quantity in recipe line"
    if unit in MASS_TO_G:
        return qty * MASS_TO_G[unit], f"{unit} converted to grams"
    if not volume_portions:
        return None, "matched food is a stand-in for nutrients only; its USDA portion weights do not apply"
    if any(re.search(rf"\b{w}\b", raw, re.I) for w in INEXACT_MEASURES):
        return None, "measure is marked heaping/scant, so the volume is not exact"
    if unit in VOLUME_TO_TSP:
        best = None
        for p in portions:
            vol = _volume_portion(p)
            if vol is None or not _qualifier_ok(vol[1], raw):
                continue
            specific = vol[1] not in NEUTRAL_QUALIFIERS
            if best is None or (specific and not best[2]):
                best = (p, vol[0], specific)
        if best:
            p, tsp, _ = best
            grams = qty * VOLUME_TO_TSP[unit] * p["grams"] / tsp
            return grams, _describe(p)
        return None, f"food has no USDA volume portion usable for '{unit}'"
    if unit is None:
        size = ing.get("size_word")
        name_words = {w.rstrip("s") for w in re.findall(r"[a-z]+", ing.get("name", ""))}
        for p in portions:
            punit, qual = _portion_parts(p["unit_desc"])
            if size and punit == size and not qual:
                return qty * p["grams"] / p["amount"], _describe(p)
            if not size and not qual and punit.rstrip("s") in name_words:
                return qty * p["grams"] / p["amount"], _describe(p)  # "22 oreo cookies" / "1 cookie"
        if size:
            return None, f"food has no USDA portion for size '{size}'"
        return None, "count without size or weight; no USDA portion to convert it"
    return None, f"unit '{unit}' has no exact gram conversion"


def nutrient_contribution(per_100g: dict, grams: float) -> dict[str, float | None]:
    return {k: (None if v is None else round(v * grams / 100.0, 3)) for k, v in per_100g.items()}
