"""Deterministic ingredient line parser: quantity, unit, size word, stated mass, clean name.

Gram weights come from two places only: a mass written in the recipe line (converted with exact
unit constants), or later from a USDA portion weight of the matched food. Nothing is guessed here.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

UNICODE_FRACTIONS = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5", "⅖": "2/5",
    "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
}

MASS_TO_G = {"g": 1.0, "kg": 1000.0, "oz": 28.349523125, "lb": 453.59237}
VOLUME_TO_TSP = {
    "tsp": 1.0, "tbsp": 3.0, "fl oz": 6.0, "cup": 48.0, "pint": 96.0, "quart": 192.0,
    "ml": 1 / 4.92892159375, "l": 1000 / 4.92892159375,
}

UNIT_ALIASES = {
    "g": "g", "gram": "g", "grams": "g", "gr": "g", "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "oz": "oz", "ounce": "oz", "ounces": "oz", "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "t": "tsp",
    "tbsp": "tbsp", "tbs": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "T": "tbsp",
    "cup": "cup", "cups": "cup", "c": "cup",
    "pint": "pint", "pints": "pint", "quart": "quart", "quarts": "quart",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "l": "l", "liter": "l",
    "liters": "l", "litre": "l",
    "pinch": "pinch", "dash": "dash", "stick": "stick", "sticks": "stick",
    "can": "can", "cans": "can", "package": "package", "packages": "package", "pkg": "package",
    "block": "block", "inch": "inch", "clove": "clove", "cloves": "clove", "slice": "slice",
    "slices": "slice", "recipe": "recipe", "jar": "jar", "box": "box", "bag": "bag",
    "square": "square", "squares": "square", "dozen": "dozen",
}
SIZE_WORDS = {"small", "medium", "large", "extra-large", "jumbo"}
HEAPING = {"heaping", "heaped", "scant", "level", "rounded"}

PREP_WORDS = {
    "softened", "melted", "chopped", "finely", "coarsely", "roughly", "sliced", "diced", "grated",
    "peeled", "divided", "sifted", "packed", "firmly", "lightly", "cold", "boiling", "warm", "hot",
    "toasted", "crushed", "drained", "mashed", "overripe", "ripe", "freshly", "pure", "very", "soft",
    "unwrapped", "room", "temperature", "at", "to", "cubed", "beaten", "lukewarm", "chilled",
    "store-bought", "homemade", "spooned", "leveled", "about", "approx", "approximately", "fine",
    "finely-ground", "pulsed", "fresh",
}
NOTE_RE = re.compile(r"\b(for (?:serving|garnish|sprinkling|greasing|dusting|topping|the pan)\b.*|optional\b.*|see note.*|plus more.*|to taste.*|if needed.*)$", re.I)

NUM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+)"
RANGE_RE = re.compile(rf"^({NUM})\s*(?:-|–|to)\s*({NUM})\b")
QTY_RE = re.compile(rf"^({NUM})(?![\d/])")
MASS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*(g|grams?|gr|kg|kilograms?|oz\.?|ounces?|lbs?|pounds?)\b", re.I)


def to_number(text: str) -> float:
    text = text.strip()
    if " " in text:
        whole, frac = text.split(None, 1)
        return float(whole) + to_number(frac)
    if "/" in text:
        n, d = text.split("/")
        return float(n) / float(d)
    return float(text)


def normalize_line(line: str) -> str:
    line = html.unescape(html.unescape(line))
    for ch, frac in UNICODE_FRACTIONS.items():
        line = re.sub(rf"(\d){ch}", rf"\1 {frac}", line)
        line = line.replace(ch, frac)
    line = line.replace("⁄", "/")
    line = re.sub(r"(\d)\s+and\s+(\d+/\d+)", r"\1 \2", line)
    line = line.replace("*", "")
    return re.sub(r"\s+", " ", line).strip()


def _mass_grams(amount: str, unit: str) -> float:
    u = unit.lower().rstrip(".")
    key = {"gram": "g", "grams": "g", "gr": "g", "kilogram": "kg", "kilograms": "kg", "ounce": "oz",
           "ounces": "oz", "lbs": "lb", "pound": "lb", "pounds": "lb"}.get(u, u)
    return float(amount) * MASS_TO_G[key]


@dataclass
class ParsedIngredient:
    raw: str
    name: str
    quantity: float | None = None
    quantity_text: str | None = None
    unit: str | None = None
    size_word: str | None = None
    stated_grams: float | None = None
    is_heading: bool = False
    notes: list[str] = field(default_factory=list)


def _strip_parens(text: str) -> tuple[str, list[str]]:
    """Remove (possibly nested) parentheticals, returning the text and their contents."""
    found = []
    out, depth, buf = [], 0, []
    for ch in text:
        if ch == "(":
            if depth == 0:
                buf = []
            else:
                buf.append(ch)
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
            if depth == 0:
                found.append("".join(buf))
            else:
                buf.append(ch)
        elif depth:
            buf.append(ch)
        else:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip(), found


def _clean_name(text: str) -> str:
    text = re.sub(r"^(optional|garnish|topping)\s*:\s*", "", text, flags=re.I)
    text = NOTE_RE.sub("", text)
    text = text.split(",")[0]
    # "X or Y" alternatives: keep one ingredient
    m = re.split(r"\s+or\s+", text, maxsplit=1, flags=re.I)
    if len(m) == 2:
        left, right = m[0].split(), m[1].split()
        if len(left) == 1 and len(right) >= 2:
            text = " ".join(right)  # "yellow or vanilla cake mix" -> "vanilla cake mix"
        elif len(left) >= 2 and len(right) >= 2 and right[-1].lower() not in (w.lower() for w in left):
            text = " ".join(left + [right[-1]])  # "graham cracker or cookie crusts"
        else:
            text = m[0]
    text = re.sub(r"\b\d+-serving\b", "", text)
    text = re.sub(r"^(?:cans?|packages?|jars?|blocks?|box|boxes|bags?)\s+(?:of\s+)?", "", text.strip(), flags=re.I)
    words = [w for w in re.split(r"\s+", text) if w]
    words = [w for w in words if w.lower().strip(".") not in PREP_WORDS and w.lower() not in SIZE_WORDS]
    name = " ".join(words).strip(" -.;:")
    return re.sub(r"\s+", " ", name).lower()


def parse_ingredient(line: str) -> ParsedIngredient:
    raw = normalize_line(line)
    if raw.endswith(":") or re.match(r"^for (the )?[\w\s]+:?$", raw, re.I) and not re.search(r"\d", raw):
        return ParsedIngredient(raw=raw, name=raw.rstrip(":").lower(), is_heading=True)

    text = re.sub(r"^(optional|garnish|topping)\s*:\s*", "", raw, flags=re.I)
    p = ParsedIngredient(raw=raw, name="")

    # "2 - 15 oz cans": a count followed by a per-item mass, not a range
    pm = re.match(r"^(\d+)\s*-\s*(?=\d+(?:\.\d+)?\s*-?\s*(?:oz\.?|ounces?|g|grams?|lbs?|pounds?)\s+(?:cans?|packages?|jars?|blocks?|boxes|box|bags?)\b)", text, re.I)
    if pm:
        text = pm.group(1) + " " + text[pm.end():]
    # leading quantity or range
    rm = RANGE_RE.match(text)
    if rm:
        p.quantity_text = rm.group(0)
        p.notes.append("quantity is a range; no single amount")
        text = text[rm.end():].strip()
    else:
        qm = QTY_RE.match(text)
        if qm:
            p.quantity = to_number(qm.group(1))
            p.quantity_text = qm.group(1)
            text = text[qm.end():].strip(" -")

    # per-item container mass right after the count: "2 (21-ounce) cans", "1 3.4-ounce package",
    # "2 - 15 oz cans", "3 (1 ounce) chocolate squares"
    per_item = None
    cm = re.match(r"^\(([^()]*)\)\s*", text)
    if cm and MASS_RE.fullmatch(cm.group(1).strip()):
        per_item = MASS_RE.fullmatch(cm.group(1).strip())
        text = text[cm.end():]
    else:
        cm = re.match(r"^(\d+(?:\.\d+)?)\s*-?\s*(oz\.?|ounces?|ounce|g|grams?|lbs?|pounds?)\b\s*(?=(?:can|cans|package|packages|pkg|block|jar|box|bag|bar)\b)", text, re.I)
        if cm and p.quantity is not None:
            per_item = cm
            text = text[cm.end():]
    if per_item is not None and p.quantity is not None:
        p.stated_grams = p.quantity * _mass_grams(per_item.group(1), per_item.group(2))
        p.notes.append(f"{p.quantity_text} x {per_item.group(0).strip()} stated in recipe")

    # unit
    um = re.match(r"^([A-Za-z]+\.?(?: oz\.?)?)\b\.?\s*", text)
    if um:
        tok = um.group(1).rstrip(".")
        if tok.lower() in ("fl oz", "fluid"):
            p.unit, text = "fl oz", text[um.end():]
        elif tok == "T" or tok.lower() in UNIT_ALIASES and tok != "T":
            p.unit = UNIT_ALIASES.get(tok, UNIT_ALIASES.get(tok.lower()))
            text = text[um.end():]
    if p.unit in HEAPING:
        p.unit = None
    words = text.split()
    while words and words[0].lower() in HEAPING:
        p.notes.append(f"'{words[0]}' measure")
        words = words[1:]
    if words and words[0].lower() in UNIT_ALIASES and p.unit is None and words[0] != "t":
        p.unit = UNIT_ALIASES[words[0].lower()]
        words = words[1:]
    if words and words[0].lower() in SIZE_WORDS:
        p.size_word = words[0].lower()
        words = words[1:]
        if words and words[0].lower() in UNIT_ALIASES and p.unit is None:
            p.unit = UNIT_ALIASES[words[0].lower()]
            words = words[1:]
    text = " ".join(words)

    name_text, parens = _strip_parens(text)
    # total mass equivalent written next to a volume or count: "2 cups (400g) sugar"
    if p.stated_grams is None and p.quantity is not None:
        for inner in parens:
            mm = MASS_RE.search(inner)
            if mm:
                p.stated_grams = _mass_grams(mm.group(1), mm.group(2))
                p.notes.append(f"mass '{mm.group(0)}' stated in recipe")
                break
    # mass unit given directly: "8 ounces cream cheese"
    if p.stated_grams is None and p.quantity is not None and p.unit in MASS_TO_G:
        p.stated_grams = p.quantity * MASS_TO_G[p.unit]
    p.name = _clean_name(name_text)
    if p.size_word is None:
        sm = re.search(r"\b(small|medium|large)\b", name_text, re.I)
        if sm:
            p.size_word = sm.group(1).lower()
    return p
