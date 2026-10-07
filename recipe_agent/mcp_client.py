"""Client side of the nutrition MCP tool: launches the server over stdio and calls its tools."""

from __future__ import annotations

import json
import sys
from contextlib import AsyncExitStack

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from .config import PROJECT_ROOT


class NutritionToolError(Exception):
    pass


class NutritionClient:
    """Async context manager. One server process per batch; `calls` counts tool invocations."""

    def __init__(self, server_params: StdioServerParameters | None = None):
        self.params = server_params or StdioServerParameters(
            command=sys.executable, args=["-m", "recipe_agent.nutrition_mcp"], cwd=str(PROJECT_ROOT)
        )
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self) -> "NutritionClient":
        self._stack = AsyncExitStack()
        self._client = await self._stack.enter_async_context(Client(self.params, read_timeout_seconds=60))
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack:
            await self._stack.aclose()

    async def list_tools(self) -> list[str]:
        result = await self._client.list_tools()
        return [t.name for t in result.tools]

    async def _call(self, name: str, args: dict) -> dict:
        self.calls.append((name, args))
        result = await self._client.call_tool(name, args)
        if result.is_error:
            text = " ".join(getattr(c, "text", "") for c in result.content)
            raise NutritionToolError(f"{name} failed: {text[:200]}")
        if result.structured_content is not None:
            data = result.structured_content
            return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
        return json.loads(result.content[0].text)

    async def search_foods(self, query: str, limit: int = 10) -> list[dict]:
        return (await self._call("search_foods", {"query": query, "limit": limit}))["candidates"]

    async def get_food(self, food_id: str) -> dict:
        return await self._call("get_food", {"food_id": food_id})
