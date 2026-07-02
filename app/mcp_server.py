"""MCP server exposing Mnemo as drop-in memory tools for any MCP client.

Run over stdio (for Claude Desktop / Qwen desktop clients):
    pipenv run python -m app.mcp_server

The five tools map 1:1 to the memory engine. `remember`/`recall` are the ones an agent
calls every turn; `forget`/`reflect` are the self-maintenance skills.
"""
from __future__ import annotations

from functools import lru_cache

from fastmcp import FastMCP

from app.memory.engine import MemoryEngine

mcp = FastMCP("Mnemo Memory")


@lru_cache
def _engine() -> MemoryEngine:
    return MemoryEngine()


@mcp.tool
def remember(text: str, user_id: str = "default", source: str | None = None) -> dict:
    """Extract and persist any durable facts from `text` for future sessions."""
    return _engine().remember(user_id, text, source=source)


@mcp.tool
def recall(query: str, user_id: str = "default", token_budget: int = 1200) -> dict:
    """Retrieve the most relevant memories for `query`, packed within `token_budget` tokens.
    Returns a ready-to-inject `context` string plus the individual memories with scores."""
    result = _engine().recall(user_id, query, token_budget=token_budget)
    return {
        "context": result["context"],
        "tokens_used": result["tokens_used"],
        "memories": [
            {"id": m["id"], "content": m["content"], "score": m["scores"]["combined"]}
            for m in result["memories"]
        ],
    }


@mcp.tool
def forget(user_id: str = "default") -> dict:
    """Run the forgetting sweep: archive stale, low-value memories."""
    return _engine().forget(user_id)


@mcp.tool
def reflect(user_id: str = "default") -> dict:
    """Consolidate near-duplicate memories into canonical facts (reflection)."""
    return _engine().reflect(user_id)


@mcp.tool
def list_memories(user_id: str = "default", status: str = "active", limit: int = 50) -> list[dict]:
    """List stored memories (with current decay scores) for inspection."""
    return _engine().list_memories(user_id, status=status, limit=limit)


if __name__ == "__main__":
    mcp.run()
