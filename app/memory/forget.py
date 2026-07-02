"""Forgetting: an Ebbinghaus-inspired decay score + a sweep that archives stale memories.

The decay score is the single knob the whole system reasons about "staleness" with. It
rewards importance and access frequency, and decays with time-since-last-access, so a
memory that keeps getting recalled stays alive while an unused one fades out.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.memory.models import Memory, MemStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def decay_score(memory: Memory, *, now: datetime | None = None, tau_days: float | None = None) -> float:
    """Return the current retention score of a memory (higher = more worth keeping)."""
    s = get_settings()
    tau_days = tau_days if tau_days is not None else s.decay_tau_days
    now = now or _utcnow()

    last = memory.last_accessed or memory.created_at or now
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_days = max((now - last).total_seconds() / 86_400.0, 0.0)

    recency = math.exp(-age_days / max(tau_days, 1e-6))
    reinforcement = 1.0 + math.log1p(max(memory.access_count, 0))
    return (memory.importance / 10.0) * recency * reinforcement


def sweep(session, user_id: str, *, threshold: float | None = None) -> dict:
    """Archive active memories whose decay score has fallen below the threshold.

    Soft-forget (status -> archived) rather than delete: safer, reversible, and lets the
    demo visualize what was forgotten and why.
    """
    s = get_settings()
    threshold = threshold if threshold is not None else s.forget_threshold
    now = _utcnow()

    rows = session.scalars(
        select(Memory).where(Memory.user_id == user_id, Memory.status == MemStatus.active)
    ).all()

    archived = []
    for m in rows:
        if decay_score(m, now=now) < threshold:
            m.status = MemStatus.archived
            archived.append(m.id)

    return {"scanned": len(rows), "archived": len(archived), "archived_ids": archived}
