import pytest

from recipe_agent.ingredient_parse import parse_ingredient


@pytest.mark.parametrize(
    "line, qty, unit, name, grams",
    [
        ("1 1/2 cups sugar", 1.5, "cup", "sugar", None),
        ("2½ cups carrots (finely grated)", 2.5, "cup", "carrots", None),
        ("1 and 1/3 cup (167g) all-purpose flour (spooned & leveled)", 4 / 3, "cup", "all-purpose flour", 167),
        ("1 cup salted butter (softened (227g))", 1, "cup", "salted butter", 227),
        ("2 (21-ounce) cans cherry pie filling", 2, "can", "cherry pie filling", 2 * 21 * 28.349523125),
        ("3 (1 ounce) unsweetened chocolate squares", 3, None, "unsweetened chocolate squares", 3 * 28.349523125),
        ("2 - 15 oz cans pumpkin puree", 2, "can", "pumpkin puree", 2 * 15 * 28.349523125),
        ("14 oz can sweetened condensed milk", 14, "oz", "sweetened condensed milk", 14 * 28.349523125),
        ("8 ounces cream cheese (softened)", 8, "oz", "cream cheese", 8 * 28.349523125),
        ("3 large eggs", 3, None, "eggs", None),
        ("1 cup buttermilk ((240ml))", 1, "cup", "buttermilk", None),  # ml is volume, not mass
        ("2 tablespoons arrowroot starch or cornstarch", 2, "tbsp", "arrowroot starch", None),
        ("1/2 cup canola oil OR melted coconut oil", 0.5, "cup", "canola oil", None),
    ],
)
def test_parse_lines(line, qty, unit, name, grams):
    p = parse_ingredient(line)
    assert p.quantity == pytest.approx(qty)
    assert p.unit == unit
    assert p.name == name
    if grams is None:
        assert p.stated_grams is None
    else:
        assert p.stated_grams == pytest.approx(grams)


def test_range_has_no_single_quantity():
    p = parse_ingredient("4-5 cups powdered sugar")
    assert p.quantity is None and p.quantity_text == "4-5" and p.name == "powdered sugar"


def test_heading_detected():
    assert parse_ingredient("For frosting:").is_heading


def test_size_word_kept_out_of_name():
    p = parse_ingredient("4 large egg yolks (room temperature)")
    assert (p.quantity, p.size_word, p.name) == (4, "large", "egg yolks")
