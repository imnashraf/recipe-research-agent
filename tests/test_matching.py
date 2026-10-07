import pytest

from recipe_agent.ingredient_parse import parse_ingredient
from recipe_agent.matching import compute_grams, initial_plan, judge
from recipe_agent.nutrition_db import load_db


def portions(food_id):
    f = load_db().get(food_id)
    return [{"amount": p.amount, "unit_desc": p.unit_desc, "grams": p.grams, "source_field": p.source_field}
            for p in f.portions]


def ing(line):
    p = parse_ingredient(line)
    return {"raw": p.raw, "name": p.name, "quantity": p.quantity, "unit": p.unit,
            "size_word": p.size_word, "stated_grams": p.stated_grams}


def test_toor_dal_plan_tries_other_names_in_order():
    plan = [s["query"] for s in initial_plan("toor dal")]
    assert plan == ["toor dal", "arhar dal", "Pigeon peas (red gram), mature seeds, raw"]


def test_toor_dal_matches_only_on_third_name():
    db = load_db()
    outcomes = []
    for step in initial_plan("toor dal"):
        hit, why = judge(db.search(step["query"]), step["strategy"], step["query"])
        outcomes.append(hit["food_id"] if hit else why)
    assert outcomes == ["no_candidates", "no_candidates", "16101"]


def test_judge_rejects_poor_and_ambiguous_hits():
    db = load_db()
    hit, why = judge(db.search("milk"), "name", "milk")  # best hit is sheep milk
    assert hit is None and "not a close match" in why
    hit, why = judge(db.search("raisins"), "name", "raisins")  # seeded vs seedless
    assert hit is None and "ambiguous" in why
    hit, _ = judge(db.search("powdered sugar"), "name", "powdered sugar")
    assert hit["food_id"] == "19336"


def test_vegan_butter_never_falls_back_to_butter():
    assert all(s["query"] != "butter" for s in initial_plan("vegan butter"))


def test_grams_from_stated_mass_wins():
    g, basis = compute_grams(ing("2 cups (400g) granulated sugar"), portions("19335"))
    assert g == 400 and basis == "mass stated in recipe line"


def test_grams_from_usda_volume_portion():
    g, basis = compute_grams(ing("3/4 cup all-purpose flour"), portions("20081"))
    assert g == pytest.approx(0.75 * 125) and "1 cup" in basis


def test_packed_qualifier_must_appear_in_recipe():
    g, basis = compute_grams(ing("1 cup light brown sugar (firmly packed)"), portions("19334"))
    assert g == pytest.approx(220) and "packed" in basis
    g, basis = compute_grams(ing("1 cup brown sugar"), portions("19334"))
    assert g == pytest.approx(48 * 3.0) and "unpacked" in basis


def test_serving_portion_with_stated_volume():
    g, _ = compute_grams(ing("1 cup vanilla ice cream"), portions("19095"))  # "1 serving, 1/2 cup" = 66 g
    assert g == pytest.approx(132)


def test_count_with_size_and_count_noun():
    assert compute_grams(ing("3 large eggs"), portions("01123"))[0] == pytest.approx(150)
    assert compute_grams(ing("24 Oreo cookies"), portions("18166"))[0] == pytest.approx(24 * 12)


def test_no_estimates():
    g, why = compute_grams(ing("2 eggs"), portions("01123"))
    assert g is None and "count without size" in why
    g, why = compute_grams(ing("1 heaping cup chopped pecans"), portions("12142"))
    assert g is None and "heaping" in why
    g, why = compute_grams(ing("3 cups almond flour"), portions("12062"), volume_portions=False)
    assert g is None and "stand-in" in why
    g, why = compute_grams(ing("salt to taste"), portions("02047"))
    assert g is None
