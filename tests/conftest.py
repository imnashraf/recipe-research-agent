import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from recipe_agent.cook_notes import ThemeSummariser  # noqa: E402
from recipe_agent.fetch import FetchError  # noqa: E402
from recipe_agent.nodes import AgentDeps  # noqa: E402
from recipe_agent.nutrition_db import load_db  # noqa: E402
from recipe_agent.run_log import RunLogger  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


@dataclass
class Page:
    html: str
    source: str
    fetched_url: str
    sha256: str


class StubFetcher:
    """Serves local fixture pages; any other URL fails like a blocked site."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def fetch(self, url):
        if url not in self.pages:
            raise FetchError(f"live fetch failed: ConnectError ({url})")
        return Page(self.pages[url], "snapshot", url, "0" * 64)


class InProcessNutrition:
    """Same data and logic as the MCP server, called in-process, with optional tool failures."""

    def __init__(self, fail_first_searches: int = 0):
        self.db = load_db()
        self.fail_first_searches = fail_first_searches
        self.calls = []

    async def search_foods(self, query, limit=10):
        self.calls.append(("search_foods", query))
        if self.fail_first_searches > 0:
            self.fail_first_searches -= 1
            raise ConnectionError("tool unavailable")
        return self.db.search(query, limit)

    async def get_food(self, food_id):
        self.calls.append(("get_food", food_id))
        f = self.db.get(food_id)
        return {
            "food_id": f.food_id, "found": True, "description": f.description,
            "nutrients_per_100g": f.nutrients_per_100g,
            "portions": [{"amount": p.amount, "unit_desc": p.unit_desc, "grams": p.grams, "source_field": p.source_field}
                         for p in f.portions],
        }


DAL_URL = "https://test-kitchen.example/toor-dal-fry/"


@pytest.fixture
def dal_html():
    return (FIXTURES / "dal_page.html").read_text()


@pytest.fixture
def make_deps(tmp_path, dal_html):
    def _make(pages=None, nutrition=None, **kw):
        return AgentDeps(
            fetcher=StubFetcher(pages if pages is not None else {DAL_URL: dal_html}),
            nutrition=nutrition or InProcessNutrition(),
            summariser=ThemeSummariser(),
            logger=RunLogger(tmp_path / "log.jsonl"),
            output_dir=tmp_path / "output",
            **kw,
        )

    return _make
