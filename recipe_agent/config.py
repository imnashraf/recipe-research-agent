"""Fixed agent parameters. These three numbers are also stated in the README."""

from pathlib import Path

# Max nutrition lookups per ingredient before it is declared unknown.
RETRY_CAP = 3

# Minimum number of cook comments (author replies excluded) needed to write a cook notes card.
COMMENT_THRESHOLD = 5

# Hard word cap for a cook notes card, enforced in code (cook_notes.enforce_word_cap).
CARD_WORD_CAP = 60

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SR28_DIR = DATA_DIR / "sr28"
OUTPUT_DIR = PROJECT_ROOT / "output"
CACHE_DIR = PROJECT_ROOT / ".cache"

NUTRITION_SOURCE = "USDA National Nutrient Database for Standard Reference, Release 28 (SR28, 2015)"
