"""Write path: turn a raw interaction into a set of salient, self-contained memories.

This is a "custom skill" — a Qwen-driven extractor that decides *what is worth
remembering*, rewrites it into a standalone statement, tags a type, and scores
importance. Extracting distilled statements (rather than storing raw turns) is what
keeps storage efficient and retrieval precise.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.qwen_client import QwenClient

_SYSTEM = (
    "You are a memory extraction module for a long-term AI memory system. "
    "Given a piece of text (a user message, a document, or a conversation turn), "
    "extract the discrete facts worth remembering across future sessions.\n"
    "Rules:\n"
    "- Each memory must be a SELF-CONTAINED statement understandable without the original context "
    "(resolve pronouns, include the subject).\n"
    "- Capture facts from BOTH speakers. The assistant's replies often carry the substance the user "
    "will later ask about — recommendations, answers, resources, specifications, names, links. Store "
    "that substance as a standalone fact, NOT as a meta-note like 'the assistant provided some links'.\n"
    "- Preserve concrete specifics VERBATIM: proper names, titles, URLs, exact numbers, dates, prices, "
    "and technical terms. Never generalize them away — write the actual title and link, not 'a video'.\n"
    "- Counts and quantities ARE the fact: when the text says how many, how much, or how long "
    "('watched all 10 comedians', 'gained 100 followers', 'a 5-hour drive'), keep the exact number "
    "in the memory. Never drop or round it.\n"
    "- When a 'Conversation date' is given, resolve EVERY relative time expression ('yesterday', "
    "'last Tuesday', 'two weeks ago', 'back in March', 'last summer', 'previously') to an ABSOLUTE "
    "date against it, write the resolved date into the memory text (e.g. 'on 2023-05-14' instead of "
    "'yesterday'), and NEVER leave a bare relative expression in the content.\n"
    "- Additionally, for each memory set 'event_date' to the ISO date (YYYY-MM-DD) when the event "
    "actually happened or the state began — NOT the conversation date, unless they coincide. This is "
    "the fact's own point in time: 'I started my new job last Monday' (conversation 2023-06-15) has "
    "event_date '2023-06-12'. When the text gives only a month or year, use the first day "
    "('back in March 2023' -> '2023-03-01'). Set event_date to null ONLY when the fact has no "
    "datable time (a standing preference, an undated trait).\n"
    "- When a turn gives a LIST of items each with its own attributes (e.g. several videos each with a "
    "title and URL, or several products each with a spec), emit ONE memory per item with its details.\n"
    "- Prefer durable facts, preferences, decisions, and entities over small talk.\n"
    "- If nothing is worth remembering, return an empty list.\n"
    "- type is one of: 'semantic' (a durable fact/preference), 'episodic' (a specific event/action), "
    "'procedural' (a how-to or standing instruction).\n"
    "- importance is an integer 1-10 (10 = critical identity/decision, 1 = trivial).\n"
    'Respond ONLY as JSON: {"memories": [{"content": str, "type": str, "importance": int, '
    '"event_date": "YYYY-MM-DD" or null}]}'
)


def extract_memories(
    client: QwenClient,
    text: str,
    *,
    cheap: bool = False,
    event_time: datetime | None = None,
) -> list[dict]:
    text = (text or "").strip()
    if not text:
        return []

    if event_time is not None:
        text = f"Conversation date: {event_time.date().isoformat()}\n\n{text}"

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
        out.append(
            {
                "content": content,
                "mem_type": mem_type,
                "importance": importance,
                "event_time": _parse_event_date(item.get("event_date")),
            }
        )
    return out


def _parse_event_date(value: object) -> datetime | None:
    """Parse the extractor's resolved ISO date into a UTC datetime, tolerantly.

    Accepts 'YYYY-MM-DD' (and full ISO timestamps). Returns None for null/blank/garbage
    so a bad value simply falls back to created_at at recall time rather than erroring.
    """
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
