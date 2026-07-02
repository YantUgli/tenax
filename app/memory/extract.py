"""Write path: turn a raw interaction into a set of salient, self-contained memories.

This is a "custom skill" — a Qwen-driven extractor that decides *what is worth
remembering*, rewrites it into a standalone statement, tags a type, and scores
importance. Extracting distilled statements (rather than storing raw turns) is what
keeps storage efficient and retrieval precise.
"""
from __future__ import annotations

from app.qwen_client import QwenClient

_SYSTEM = (
    "You are a memory extraction module for a long-term AI memory system. "
    "Given a piece of text (a user message, a document, or a conversation turn), "
    "extract the discrete facts worth remembering across future sessions.\n"
    "Rules:\n"
    "- Each memory must be a SELF-CONTAINED statement understandable without the original context "
    "(resolve pronouns, include the subject).\n"
    "- Prefer durable facts, preferences, decisions, and entities over small talk.\n"
    "- If nothing is worth remembering, return an empty list.\n"
    "- type is one of: 'semantic' (a durable fact/preference), 'episodic' (a specific event/action), "
    "'procedural' (a how-to or standing instruction).\n"
    "- importance is an integer 1-10 (10 = critical identity/decision, 1 = trivial).\n"
    'Respond ONLY as JSON: {"memories": [{"content": str, "type": str, "importance": int}]}'
)


def extract_memories(client: QwenClient, text: str, *, cheap: bool = False) -> list[dict]:
    text = (text or "").strip()
    if not text:
        return []

    data = client.chat_json(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
        cheap=cheap,
    )

    raw = data.get("memories", []) if isinstance(data, dict) else data
    out: list[dict] = []
    for item in raw or []:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        mem_type = item.get("type", "episodic")
        if mem_type not in ("semantic", "episodic", "procedural"):
            mem_type = "episodic"
        try:
            importance = float(item.get("importance", 5))
        except (TypeError, ValueError):
            importance = 5.0
        importance = min(max(importance, 1.0), 10.0)
        out.append({"content": content, "mem_type": mem_type, "importance": importance})
    return out
