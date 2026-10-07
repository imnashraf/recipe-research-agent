"""Check 4: hand-check three recipes' nutrition against their food ids.

Independently of the agent's code path, this reads the raw USDA SR28 ABBREV.txt line for each
food id, re-derives the gram weight from the cited basis (stated mass, mass unit, or the USDA
portion field the record names), recomputes energy/protein/fat/carbohydrate/sodium and compares.

    python evals/nutrition_handcheck.py
"""

import re
import sys

from _common import REPORTS, ROOT, dataset, md_table

RECIPES = ["Southern Fudge Pie", "Banana Cream Pie Recipe", "Paleo Gingerbread"]
FIELDS = {"energy_kcal": 3, "protein_g": 4, "fat_g": 5, "carbohydrate_g": 7, "sodium_mg": 15}
MASS = {"g": 1.0, "kg": 1000.0, "oz": 28.349523125, "lb": 453.59237}
TSP = {"tsp": 1, "tbsp": 3, "fl oz": 6, "cup": 48, "pint": 96, "quart": 192}


def abbrev_line(food_id: str) -> list[str]:
    with open(ROOT / "data" / "sr28" / "ABBREV.txt", encoding="latin-1") as fh:
        for line in fh:
            if line.startswith(f"~{food_id}~"):
                return line.rstrip("\r\n").split("^")
    raise KeyError(food_id)


def grams_by_hand(ing: dict, row: list[str]) -> float:
    basis = ing["gram_basis"]
    if basis == "mass stated in recipe line":
        nums = re.findall(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\b", ing["raw"])
        if nums:
            return float(nums[0])
        m = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*(?:oz|ounces?)", ing["raw"])
        return ing["quantity"] * float(m.group(1)) * MASS["oz"]
    if basis.endswith("converted to grams"):
        return ing["quantity"] * MASS[ing["unit"]]
    m = re.match(r"USDA portion '([\d.]+) (.+)' = ([\d.]+) g \((GmWt_[12])\)", basis)
    amount, desc, grams, field = float(m.group(1)), m.group(2), float(m.group(3)), m.group(4)
    gcol, dcol = (48, 49) if field == "GmWt_1" else (50, 51)
    usda_desc = re.sub(r"\s+", " ", row[dcol].strip("~"))
    assert float(row[gcol]) == grams and usda_desc == re.sub(r"\s+", " ", f"{row[dcol].strip('~').split()[0]} {desc}"), (row[gcol], row[dcol])
    assert float(usda_desc.split()[0]) == amount
    if ing["unit"] in TSP:
        m2 = re.match(r"serving, ([\d/]+) (cup|tbsp|tsp)", desc)
        if m2:
            n = m2.group(1)
            vol = eval(n) * TSP[m2.group(2)] * amount  # noqa: S307 (fraction literal from the USDA file)
        else:
            unit = desc.split(",")[0].split(" ")[0]
            unit = {"tablespoon": "tbsp", "teaspoon": "tsp"}.get(unit, unit)
            vol = amount * TSP["fl oz" if desc.startswith("fl oz") else unit]
        return ing["quantity"] * TSP[ing["unit"]] * grams / vol
    return ing["quantity"] * grams / amount


def main() -> int:
    ds = dataset()
    out = ["# Check 4: nutrition hand-check against food ids", "",
           "For each ingredient with nutrition, the raw SR28 `ABBREV.txt` line for its food id was read directly "
           "(not through the agent's database module), the gram weight re-derived from the basis the record cites, "
           "and the nutrient contribution recomputed as value_per_100g × grams / 100.", ""]
    worst = 0.0
    for title in RECIPES:
        rec = next(r for r in ds["recipes"] if r["title"] == title)
        rows = []
        for ing in rec["ingredients"]:
            if ing["nutrition_status"] != "computed":
                rows.append([ing["raw"], ing["food_id"] or "-", "-", "-", "-", "-", ing["nutrition_status"]])
                continue
            row = abbrev_line(ing["food_id"])
            g = grams_by_hand(ing, row)
            kcal = float(row[FIELDS["energy_kcal"]]) * g / 100
            diffs = [abs(g - ing["grams"])]
            for k, col in FIELDS.items():
                raw = row[col]
                if raw:
                    diffs.append(abs(float(raw) * g / 100 - ing["nutrients"][k]))
            worst = max(worst, max(diffs))
            rows.append([ing["raw"], ing["food_id"], row[1].strip("~"), f"{g:.1f}", f"{float(row[3]):g}",
                         f"{kcal:.1f} / {ing['nutrients']['energy_kcal']:.1f}", "match" if max(diffs) < 0.06 else "MISMATCH"])
        tot = rec["nutrition"]["totals"]["energy_kcal"]
        hand_tot = sum(float(r[5].split(" / ")[0]) for r in rows if r[6] == "match")
        out += [f"## {title} ({rec['recipe_id']})", "", rec["nutrition"]["statement"], "",
                md_table(rows, ["ingredient", "food id", "SR28 short description", "grams (hand)", "kcal/100 g",
                                "kcal hand / record", "result"]), "",
                f"Recipe total energy: record {tot} kcal, hand sum {hand_tot:.1f} kcal.", ""]
    out += [f"Largest absolute difference across grams and nutrients: {worst:.4f} (rounding only).", ""]
    (REPORTS / "04_nutrition_handcheck.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    return 0 if worst < 0.06 else 1


if __name__ == "__main__":
    sys.exit(main())
