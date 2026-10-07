"""MCP server exposing the USDA SR28 food composition data as two tools.

Run standalone:  python -m recipe_agent.nutrition_mcp   (stdio transport)

Tools
  search_foods(query, limit) -> ranked candidate foods (food_id, description, cost)
  get_food(food_id)          -> nutrients per 100 g and USDA household portion weights
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .config import NUTRITION_SOURCE
from .nutrition_db import load_db

server = MCPServer(
    name="usda-sr28-nutrition",
    instructions="Look up foods in USDA SR28. Search first, then fetch a food by its food_id.",
)


@server.tool()
def search_foods(query: str, limit: int = 10) -> dict:
    """Search USDA SR28 foods whose description contains every word of the query.

    Results are ranked by cost (0 = description uses only the query's words; higher means
    more unrequested descriptors, a different leading food name, or a branded product).
    """
    limit = max(1, min(int(limit), 25))
    return {"query": query, "source": NUTRITION_SOURCE, "candidates": load_db().search(query, limit)}


@server.tool()
def get_food(food_id: str) -> dict:
    """Nutrients per 100 g edible portion and USDA household portion weights for one food."""
    food = load_db().get(food_id)
    if food is None:
        return {"food_id": food_id, "found": False}
    return {
        "food_id": food.food_id,
        "found": True,
        "description": food.description,
        "food_group": food.group,
        "source": NUTRITION_SOURCE,
        "nutrients_per_100g": food.nutrients_per_100g,
        "portions": [
            {"amount": p.amount, "unit_desc": p.unit_desc, "grams": p.grams, "source_field": p.source_field}
            for p in food.portions
        ],
    }


def main() -> None:
    load_db()  # parse the data files once before serving
    server.run("stdio")


if __name__ == "__main__":
    main()
