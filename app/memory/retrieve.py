"""Read path: hybrid retrieval + context-budget-aware selection.

Two ideas do the heavy lifting for Track 1:

1. Hybrid scoring — dense (embedding) + sparse (Postgres full-text) + recency + importance,
   combined into one relevance score. Neither vector nor keyword search alone is robust;
   together they recover both paraphrases and exact-term matches.

2. Budget-aware selection — given a token budget (the slice of the context window we're
   willing to spend on memory), greedily pack the highest-relevance memories that fit.
   This is the direct answer to "recall critical memories in a limited context window".
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np
import tiktoken
from sqlalchemy import and_, func, or_, select

from app.config import get_settings
from app.memory.models import Memory, MemStatus
from app.qwen_client import QwenClient

# Superseded facts are served back (tagged PAST) so history questions stay answerable,
# but they must never outrank their replacement or crowd active facts out of the budget.
_PAST_SCORE_FACTOR = 0.9
_MAX_PAST_FACTS = 5

# Facts archived by belief revision (superseded_by set) stay visible as history;
# facts archived by decay stay hidden.
_VISIBLE = or_(
    Memory.status == MemStatus.active,
    and_(Memory.status == MemStatus.archived, Memory.superseded_by.is_not(None)),
)


@lru_cache
def _encoder():
    # cl100k_base is a good, fast proxy for budgeting; Qwen's exact tokenizer differs slightly.
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text or "", disallowed_special=()))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def _anchor(m: Memory):
    """The date the fact is anchored to for temporal reasoning: its own event_time when
    the extractor resolved one, else created_at (record/session time). This is what the
    reader sees and orders by — so duration/ordering questions reason over *when things
    happened*, not when Tenax logged them."""
    return m.event_time or m.created_at


def _render_line(m: Memory, successor_created: dict) -> str:
    anchor = _anchor(m)
    prefix = f"[{anchor.date().isoformat()}] " if anchor else ""
    if m.status == MemStatus.archived:
        succ = successor_created.get(m.superseded_by)
        note = (
            f"PAST (superseded on {succ.date().isoformat()})" if succ else "PAST (later superseded)"
        )
        return f"- {prefix}{note}: {m.content}"
    return f"- {prefix}{m.content}"


def _chrono_key(m: Memory) -> float:
    dt = _anchor(m)
    if dt is None:
        return float("inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _pack(scored: list[dict], token_budget: int, lam: float) -> tuple[list[dict], int]:
    """Greedily pack the budget by Maximal Marginal Relevance.

    Each round picks the candidate maximising ``lam * relevance - (1-lam) * redundancy``,
    where redundancy is the highest cosine similarity to anything already selected. This
    keeps a cluster of topic-adjacent memories from consuming the budget and starving a
    multi-fact question of its second fact. ``lam = 1.0`` is exactly the old pure-relevance
    packing. Redundancy is tracked incrementally (one vectorised pass per pick), so this
    costs O(n * picks) similarities rather than recomputing a full matrix each round.
    """
    if not scored:
        return [], 0

    embs = np.stack([it["embedding"] for it in scored]).astype(np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    embs = embs / np.where(norms == 0.0, 1e-9, norms)

    relevance = np.array([it["score"] for it in scored], dtype=np.float32)
    redundancy = np.zeros(len(scored), dtype=np.float32)
    alive = np.ones(len(scored), dtype=bool)

    selected: list[dict] = []
    used = past_used = 0

    while True:
        fits = np.array(
            [
                alive[i]
                and used + it["tokens"] <= token_budget
                and not (it["is_past"] and past_used >= _MAX_PAST_FACTS)
                for i, it in enumerate(scored)
            ]
        )
        if not fits.any():
            break

        value = lam * relevance - (1.0 - lam) * redundancy
        value = np.where(fits, value, -np.inf)
        pick = int(np.argmax(value))

        item = scored[pick]
        selected.append(item)
        used += item["tokens"]
        past_used += item["is_past"]
        alive[pick] = False
        if lam < 1.0:
            redundancy = np.maximum(redundancy, embs @ embs[pick])

    return selected, used


def retrieve(
    session,
    client: QwenClient,
    user_id: str,
    query: str,
    *,
    token_budget: int | None = None,
    candidate_k: int = 30,
    reinforce: bool = True,
) -> dict:
    s = get_settings()
    token_budget = token_budget if token_budget is not None else s.default_token_budget
    now = datetime.now(timezone.utc)

    qvec = np.asarray(client.embed_one(query), dtype=np.float32)

    # --- candidate generation (two indexes) ---
    vec_ids = session.scalars(
        select(Memory.id)
        .where(Memory.user_id == user_id, _VISIBLE)
        .order_by(Memory.embedding.cosine_distance(qvec.tolist()))
        .limit(candidate_k)
    ).all()

    tsv = func.to_tsvector("english", Memory.content)
    tsq = func.plainto_tsquery("english", query)
    kw_rows = session.execute(
        select(Memory.id, func.ts_rank(tsv, tsq).label("rank"))
        .where(Memory.user_id == user_id, _VISIBLE, tsv.op("@@")(tsq))
        .order_by(func.ts_rank(tsv, tsq).desc())
        .limit(candidate_k)
    ).all()
    kw_rank = {row.id: float(row.rank) for row in kw_rows}

    candidate_ids = list(dict.fromkeys([*vec_ids, *kw_rank.keys()]))
    if not candidate_ids:
        return {"memories": [], "context": "", "tokens_used": 0, "token_budget": token_budget}

    rows = session.scalars(select(Memory).where(Memory.id.in_(candidate_ids))).all()

    successor_ids = {m.superseded_by for m in rows if m.superseded_by is not None}
    successor_created = (
        dict(
            session.execute(
                select(
                    Memory.id,
                    func.coalesce(Memory.event_time, Memory.created_at),
                ).where(Memory.id.in_(successor_ids))
            ).all()
        )
        if successor_ids
        else {}
    )

    # --- unified scoring ---
    max_rank = max(kw_rank.values(), default=0.0) or 1.0
    scored = []
    for m in rows:
        emb = np.asarray(m.embedding, dtype=np.float32)
        semantic = max(0.0, _cosine(qvec, emb))
        keyword = kw_rank.get(m.id, 0.0) / max_rank

        last = m.last_accessed or m.created_at or now
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_days = max((now - last).total_seconds() / 86_400.0, 0.0)
        recency = math.exp(-age_days / max(s.decay_tau_days, 1e-6))

        importance = m.importance / 10.0
        combined = (
            s.w_semantic * semantic
            + s.w_keyword * keyword
            + s.w_recency * recency
            + s.w_importance * importance
        )
        is_past = m.status == MemStatus.archived
        if is_past:
            combined *= _PAST_SCORE_FACTOR
        line = _render_line(m, successor_created)
        scored.append(
            {
                "memory": m,
                "score": combined,
                "semantic": semantic,
                "keyword": keyword,
                "recency": recency,
                "importance": importance,
                "is_past": is_past,
                "line": line,
                "embedding": emb,
                "tokens": count_tokens(line) + 1,  # +1 for the joining newline
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)

    # --- budget-aware selection (MMR: relevance minus redundancy, packed to budget) ---
    selected, used = _pack(scored, token_budget, s.mmr_lambda)

    if reinforce and selected:
        ids = [it["memory"].id for it in selected]
        session.execute(
            Memory.__table__.update()
            .where(Memory.id.in_(ids))
            .values(access_count=Memory.access_count + 1, last_accessed=now)
        )

    memories = []
    for it in selected:
        d = it["memory"].as_dict()
        d["scores"] = {
            "combined": round(it["score"], 4),
            "semantic": round(it["semantic"], 4),
            "keyword": round(it["keyword"], 4),
            "recency": round(it["recency"], 4),
            "importance": round(it["importance"], 4),
        }
        d["tokens"] = it["tokens"]
        memories.append(d)

    # Selection is greedy-by-score, but the context reads chronologically: dated lines in
    # time order let the reader do ordering/duration reasoning directly.
    context = "\n".join(
        it["line"] for it in sorted(selected, key=lambda it: _chrono_key(it["memory"]))
    )
    return {
        "memories": memories,
        "context": context,
        "tokens_used": used,
        "token_budget": token_budget,
        "candidates_considered": len(scored),
    }
