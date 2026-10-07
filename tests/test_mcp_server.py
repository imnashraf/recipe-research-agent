"""Real stdio round trip to the nutrition MCP server."""

import asyncio

from recipe_agent.mcp_client import NutritionClient


def test_mcp_tools_over_stdio():
    async def go():
        async with NutritionClient() as c:
            assert sorted(await c.list_tools()) == ["get_food", "search_foods"]
            hits = await c.search_foods("powdered sugar", 3)
            food = await c.get_food(hits[0]["food_id"])
            missing = await c.get_food("00000")
            return hits, food, missing

    hits, food, missing = asyncio.run(go())
    assert hits[0]["food_id"] == "19336"
    assert food["description"] == "Sugars, powdered" and food["nutrients_per_100g"]["energy_kcal"] == 389
    assert {"amount": 1.0, "unit_desc": "cup, unsifted", "grams": 120.0, "source_field": "GmWt_1"} in food["portions"]
    assert missing == {"food_id": "00000", "found": False}
