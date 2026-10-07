"""Compile output/dataset.json into a PDF, plus a JSON summary used to draft the hand-off email.

    python -m recipe_agent.report            # writes output/recipe_dataset.pdf
"""

from __future__ import annotations

import io
import json
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import OUTPUT_DIR


def load_dataset(path: Path = OUTPUT_DIR / "dataset.json") -> dict:
    return json.loads(path.read_text())


def summarize(ds: dict) -> dict:
    recipes = ds["recipes"]
    ings = [i for r in recipes for i in r["ingredients"]]
    matched = sum(i["status"] == "matched" for i in ings)
    with_n = sum(i["nutrition_status"] == "computed" for i in ings)
    return {
        "category": ds["category"],
        "recipes": len(recipes),
        "terminal_states": dict(Counter(r["terminal"]["state"] for r in recipes)),
        "ingredients": len(ings),
        "matched": matched,
        "match_rate": round(matched / len(ings), 3) if ings else 0,
        "ingredients_with_nutrition": with_n,
        "unknown": len(ings) - matched,
        "hit_retry_cap": sum(r["match"]["hit_retry_cap"] for r in recipes),
        "cards_produced": sum(r["cook_notes"]["status"] == "produced" for r in recipes),
        "cards_skipped": sum(r["cook_notes"]["status"] != "produced" for r in recipes),
        "retry_cap": ds["retry_cap"],
        "comment_threshold": ds["comment_threshold"],
        "card_word_cap": ds["card_word_cap"],
    }


def _p(text, style):
    return Paragraph(escape(str(text)), style)


def build_pdf(ds: dict) -> bytes:
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=7.5, leading=9)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=11.5)
    card = ParagraphStyle("card", parent=body, backColor=colors.HexColor("#f3f0e8"), borderPadding=5)
    s = summarize(ds)
    grid = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ])
    story = [
        _p(f"Recipe Research Agent: {s['category']} dataset", styles["Title"]),
        _p(f"{s['recipes']} recipes, {s['ingredients']} ingredient lines. Matched to a USDA SR28 food id: "
           f"{s['matched']} ({s['match_rate']:.1%}). With a gram weight and nutrition: {s['ingredients_with_nutrition']}. "
           f"Unknown: {s['unknown']} ({s['hit_retry_cap']} reached the retry cap).", body),
        _p(f"Terminal states: {', '.join(f'{k} {v}' for k, v in sorted(s['terminal_states'].items()))}. "
           f"Cook notes cards: {s['cards_produced']} produced, {s['cards_skipped']} skipped (fewer than "
           f"{s['comment_threshold']} comments).", body),
        _p(f"Parameters: retry cap {s['retry_cap']} lookups per ingredient; comment threshold {s['comment_threshold']}; "
           f"card cap {s['card_word_cap']} words. Unmatched ingredients are recorded as unknown, never estimated; "
           "recipe totals marked Partial exclude them.", body),
        Spacer(1, 4 * mm),
    ]
    rows = [["#", "Recipe", "Recipe id", "Matched", "Nutrition", "kcal (whole)", "Card"]]
    for n, r in enumerate(ds["recipes"], 1):
        nut = r["nutrition"]
        rows.append([
            n, _p(r["title"], small), r["recipe_id"], f"{r['match']['matched']}/{r['match']['ingredients']}",
            "complete" if nut["complete"] else f"partial ({nut['ingredients_with_nutrition']}/{nut['ingredients_total']})",
            f"{nut['totals']['energy_kcal']:.0f}", "yes" if r["cook_notes"]["status"] == "produced" else "no",
        ])
    story.append(Table(rows, colWidths=[7 * mm, 62 * mm, 26 * mm, 16 * mm, 26 * mm, 20 * mm, 12 * mm], style=grid, repeatRows=1))

    for r in ds["recipes"]:
        nut = r["nutrition"]
        story += [PageBreak(), _p(r["title"], styles["Heading2"]),
                  _p(f"Recipe id {r['recipe_id']} | {r['source_url']}", small),
                  _p(f"Yield: {r['yield_text'] or 'not stated'} | Terminal: {r['terminal']['state']} ({r['terminal']['reason']})", small),
                  Spacer(1, 2 * mm), _p(nut["statement"], body)]
        t = nut["totals"]
        line = (f"Whole recipe: {t['energy_kcal']:.0f} kcal, protein {t['protein_g']:.1f} g, fat {t['fat_g']:.1f} g, "
                f"carbohydrate {t['carbohydrate_g']:.1f} g, sugars {t['sugars_g']:.1f} g, sodium {t['sodium_mg']:.0f} mg.")
        if nut["per_serving"]:
            ps = nut["per_serving"]
            unit = (r["servings_unit"] or "servings").rstrip("s") or "serving"
            line += f" Per {unit} ({r['servings']} per recipe): {ps['energy_kcal']:.0f} kcal (partial if the total is)."
        story += [_p(line, body), Spacer(1, 2 * mm)]
        rows = [["Ingredient (as written)", "USDA food id", "Food", "Grams", "kcal", "Status"]]
        for i in r["ingredients"]:
            status = i["status"] if i["nutrition_status"] == "computed" else (
                "no gram weight" if i["status"] == "matched" else "unknown")
            rows.append([
                _p(i["raw"], small), i["food_id"] or "-", _p(i["food_description"] or "-", small),
                f"{i['grams']:.0f}" if i["grams"] is not None else "-",
                f"{i['nutrients']['energy_kcal']:.0f}" if i["nutrients"] and i["nutrients"].get("energy_kcal") is not None else "-",
                status,
            ])
        story.append(Table(rows, colWidths=[58 * mm, 17 * mm, 52 * mm, 13 * mm, 11 * mm, 22 * mm], style=grid, repeatRows=1))
        story.append(Spacer(1, 3 * mm))
        notes = r["cook_notes"]
        if notes["status"] == "produced":
            story.append(_p(notes["card"], card))
            ids = "; ".join(f"{c['text']}: {', '.join(c['comment_ids'])}" for c in notes["claims"])
            story.append(_p(f"Comment ids behind each claim: {ids}", small))
        else:
            story.append(_p(f"No cook notes card: {notes['comment_count']} comments, below the threshold of {notes['threshold']}.", body))

    story += [PageBreak(), _p("Appendix: unmatched ingredients", styles["Heading2"])]
    rows = [["Recipe id", "Ingredient", "Queries tried", "Reason"]]
    for r in ds["recipes"]:
        for i in r["ingredients"]:
            if i["status"] == "unknown":
                rows.append([r["recipe_id"], _p(i["raw"], small), _p(" | ".join(i["queries_tried"]), small),
                             _p(i["unknown_reason"], small)])
    story.append(Table(rows, colWidths=[24 * mm, 50 * mm, 50 * mm, 52 * mm], style=grid, repeatRows=1))

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm,
                      bottomMargin=14 * mm, title=f"{ds['category']} recipe dataset",
                      author="recipe-research-agent").build(story)
    return buf.getvalue()


def main(argv=None) -> int:
    ds = load_dataset()
    out = OUTPUT_DIR / "recipe_dataset.pdf"
    out.write_bytes(build_pdf(ds))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    print(json.dumps(summarize(ds), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
