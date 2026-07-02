"""Consolidation ("reflection"): cluster near-duplicate memories and distill them.

Over time an agent accumulates many overlapping episodic memories. Reflection groups
semantically similar ones and asks Qwen to distill each group into a small set of
canonical semantic facts, then archives the sources (superseded_by -> new fact). This
shrinks storage and sharpens retrieval precision — the "efficiency" the track rewards.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy import select

from app.config import get_settings
from app.memory.models import Memory, MemStatus, MemType
from app.qwen_client import QwenClient

_SYSTEM = (
    "You merge several related memory statements into the smallest set of canonical, "
    "non-redundant facts. Preserve every distinct piece of information; drop duplicates; "
    "if statements conflict, prefer the most recent. Keep each fact self-contained.\n"
    'Respond ONLY as JSON: {"facts": [str, ...]}'
)

_MAX_MEMORIES = 300  # cap work per reflection pass


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1e-9
    return mat / norms


def _cluster(rows: list[Memory], threshold: float) -> list[list[int]]:
    """Greedy single-pass clustering by cosine similarity; returns lists of row indices."""
    if not rows:
        return []
    mat = _normalize(np.asarray([r.embedding for r in rows], dtype=np.float32))
    sims = mat @ mat.T
    assigned = [False] * len(rows)
    clusters: list[list[int]] = []
    for i in range(len(rows)):
        if assigned[i]:
            continue
        members = [i]
        assigned[i] = True
        for j in range(i + 1, len(rows)):
            if not assigned[j] and sims[i, j] >= threshold:
                members.append(j)
                assigned[j] = True
        clusters.append(members)
    return clusters


def consolidate(session, client: QwenClient, user_id: str, *, threshold: float | None = None) -> dict:
    s = get_settings()
    threshold = threshold if threshold is not None else s.consolidate_similarity

    rows = session.scalars(
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.status == MemStatus.active,
            Memory.mem_type != MemType.procedural,  # keep standing instructions intact
        )
        .order_by(Memory.created_at.desc())
        .limit(_MAX_MEMORIES)
    ).all()

    clusters = _cluster(rows, threshold)
    merged_ids: list[int] = []
    new_facts: list[str] = []

    for members in clusters:
        if len(members) < 2:
            continue
        group = [rows[i] for i in members]
        group.sort(key=lambda m: m.created_at)  # oldest -> newest for "prefer recent"
        bullet = "\n".join(f"- ({m.created_at.date()}) {m.content}" for m in group)

        data = client.chat_json(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": bullet},
            ]
        )
        facts = [f.strip() for f in (data.get("facts", []) if isinstance(data, dict) else []) if f.strip()]
        if not facts:
            continue

        importance = max(m.importance for m in group)
        embeddings = client.embed(facts)
        created: list[Memory] = []
        for fact, emb in zip(facts, embeddings):
            mem = Memory(
                user_id=user_id,
                content=fact,
                mem_type=MemType.semantic,
                importance=importance,
                embedding=emb,
                access_count=sum(m.access_count for m in group),
                source="consolidation",
            )
            session.add(mem)
            created.append(mem)
        session.flush()  # assign ids to created rows

        new_id = created[0].id
        for m in group:
            m.status = MemStatus.archived
            m.superseded_by = new_id
            merged_ids.append(m.id)
        new_facts.extend(facts)

    return {
        "clusters_found": sum(1 for c in clusters if len(c) >= 2),
        "memories_merged": len(merged_ids),
        "semantic_created": len(new_facts),
        "merged_ids": merged_ids,
    }
