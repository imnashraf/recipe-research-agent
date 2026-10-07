"""USDA SR28 food composition data: loading, token search and portion weights.

Only the MCP server (nutrition_mcp.py) imports this module. The agent reaches the data through
the MCP tools, never directly.

Food ids are SR28 NDB numbers (e.g. "20081" = Wheat flour, white, all-purpose, enriched, bleached).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import SR28_DIR

# ABBREV.txt column positions (SR28 documentation, "Abbreviated file" layout, 53 fields).
NUTRIENT_COLUMNS = {
    "energy_kcal": 3,
    "protein_g": 4,
    "fat_g": 5,
    "carbohydrate_g": 7,
    "fiber_g": 8,
    "sugars_g": 9,
    "sodium_mg": 15,
    "saturated_fat_g": 44,
    "cholesterol_mg": 47,
}
GMWT_1, GMWT_DESC_1, GMWT_2, GMWT_DESC_2 = 48, 49, 50, 51

# Food groups left out of search: baby foods, fast foods, mixed meals, regional, restaurant foods.
EXCLUDED_GROUPS = {"0300", "2100", "2200", "3500", "3600"}

STOPWORDS = {"and", "or", "of", "the", "a", "with", "in", "for"}

# Descriptor words that describe the default form of a food; they cost little when unrequested.
DEFAULT_FORM_TOKENS = {
    "raw", "fresh", "whole", "regular", "plain", "enriched", "bleached", "granulated",
    "salted", "commercial", "prepared", "dry", "ground", "mature", "seed", "fluid",
    "sweetened", "unprepared", "solid",
}


def _singular(tok: str) -> str:
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith(("ches", "shes", "oes")):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def tokenize(text: str) -> list[str]:
    return [_singular(t) for t in re.findall(r"[a-z0-9]+", text.lower().replace("'", ""))]


@dataclass(frozen=True)
class Portion:
    amount: float
    unit_desc: str  # e.g. "cup", "tbsp", "large", "cup, packed"
    grams: float
    source_field: str  # GmWt_1 or GmWt_2


@dataclass(frozen=True)
class Food:
    food_id: str
    description: str
    common_names: str
    group: str
    nutrients_per_100g: dict[str, float | None]
    portions: tuple[Portion, ...]

    @property
    def tokens(self) -> set[str]:
        return set(tokenize(self.description)) | set(tokenize(self.common_names))

    @property
    def is_branded(self) -> bool:
        # SR28 writes brand names in capitals (e.g. "HERSHEY'S", "KRAFT").
        return bool(re.search(r"\b[A-Z][A-Z']{2,}\b", self.description))


def _field(raw: str) -> str:
    return raw.strip().strip("~").strip()


def _num(raw: str) -> float | None:
    raw = _field(raw)
    return float(raw) if raw else None


_PORTION_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s+(.*)$")


def _portion(grams_raw: str, desc_raw: str, field: str) -> Portion | None:
    grams, desc = _num(grams_raw), _field(desc_raw)
    if not grams or not desc:
        return None
    m = _PORTION_RE.match(desc)
    if not m:
        return None
    unit = re.sub(r"\s+", " ", m.group(2)).strip()
    return Portion(amount=float(m.group(1)), unit_desc=unit, grams=grams, source_field=field)


class FoodDatabase:
    def __init__(self, sr28_dir: Path = SR28_DIR):
        des: dict[str, list[str]] = {}
        with open(sr28_dir / "FOOD_DES.txt", encoding="latin-1") as fh:
            for line in fh:
                parts = line.rstrip("\r\n").split("^")
                des[_field(parts[0])] = parts
        self.foods: dict[str, Food] = {}
        with open(sr28_dir / "ABBREV.txt", encoding="latin-1") as fh:
            for line in fh:
                p = line.rstrip("\r\n").split("^")
                food_id = _field(p[0])
                d = des[food_id]
                portions = tuple(
                    x
                    for x in (
                        _portion(p[GMWT_1], p[GMWT_DESC_1], "GmWt_1"),
                        _portion(p[GMWT_2], p[GMWT_DESC_2], "GmWt_2"),
                    )
                    if x
                )
                self.foods[food_id] = Food(
                    food_id=food_id,
                    description=_field(d[2]),
                    common_names=_field(d[4]),
                    group=_field(d[1]),
                    nutrients_per_100g={k: _num(p[i]) for k, i in NUTRIENT_COLUMNS.items()},
                    portions=portions,
                )
        self._token_index: dict[str, set[str]] = {}
        for food in self.foods.values():
            if food.group in EXCLUDED_GROUPS:
                continue
            for tok in food.tokens:
                self._token_index.setdefault(tok, set()).add(food.food_id)

    def get(self, food_id: str) -> Food | None:
        return self.foods.get(food_id)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Foods containing every query token, best first.

        Ranking cost: unrequested descriptor tokens (default-form words cost less), branded
        descriptions and foods whose leading descriptor segment is not part of the query.
        """
        q = [t for t in tokenize(query) if t not in STOPWORDS]
        if not q:
            return []
        ids = set.intersection(*(self._token_index.get(t, set()) for t in q))
        qset = set(q)
        scored = []
        for fid in ids:
            food = self.foods[fid]
            desc_tokens = tokenize(food.description)
            extra = [t for t in desc_tokens if t not in qset and t not in STOPWORDS]
            cost = sum(0.3 if t in DEFAULT_FORM_TOKENS else 1.0 for t in extra)
            head = set(tokenize(food.description.split(",")[0]))
            if not head <= qset:
                cost += 2.0
            if food.is_branded:
                cost += 3.0
            scored.append((round(cost, 2), len(food.description), fid))
        scored.sort()
        return [
            {
                "food_id": fid,
                "description": self.foods[fid].description,
                "common_names": self.foods[fid].common_names,
                "food_group": self.foods[fid].group,
                "cost": cost,
            }
            for cost, _, fid in scored[:limit]
        ]


@lru_cache(maxsize=1)
def load_db() -> FoodDatabase:
    return FoodDatabase()
