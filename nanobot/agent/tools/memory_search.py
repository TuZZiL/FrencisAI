"""Memory search tool: semantic search over agent memory."""

from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.agent.memory import MemoryStore


class MemorySearchTool(Tool):
    """Search the agent's memory archive semantically."""

    name = "memory_search"
    description = (
        "Search your memory archive (daily notes and long-term memory) semantically. "
        "Use this when you need to recall past conversations, decisions, or facts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in memory",
            },
            "count": {
                "type": "integer",
                "description": "Number of results (1-20)",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    }

    def __init__(self, memory: MemoryStore):
        self._memory = memory

    async def execute(self, query: str, count: int = 10, **kwargs: Any) -> str:
        return self._memory.search_memory(query, n_results=count)
