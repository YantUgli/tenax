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
from sqlalchemy import func, select

from app.config import get_settings
from app.memory.models import Memory, MemStatus
from app.qwen_client import QwenClient


@lru_cache
def _encoder():
    # cl100k_base is a good, fast proxy for budgeting; Qwen's exact tokenizer differs slightly.
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text or "", disallowed_special=()))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


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
        .where(Memory.user_id == user_id, Memory.status == MemStatus.active)
        .order_by(Memory.embedding.cosine_distance(qvec.tolist()))
        .limit(candidate_k)
    ).all()

    tsv = func.to_tsvector("english", Memory.content)
    tsq = func.plainto_tsquery("english", query)
    kw_rows = session.execute(
        select(Memory.id, func.ts_rank(tsv, tsq).label("rank"))
        .where(Memory.user_id == user_id, Memory.status == MemStatus.active, tsv.op("@@")(tsq))
        .order_by(func.ts_rank(tsv, tsq).desc())
        .limit(candidate_k)
    ).all()
    kw_rank = {row.id: float(row.rank) for row in kw_rows}

    candidate_ids = list(dict.fromkeys([*vec_ids, *kw_rank.keys()]))
    if not candidate_ids:
        return {"memories": [], "context": "", "tokens_used": 0, "token_budget": token_budget}

    rows = session.scalars(select(Memory).where(Memory.id.in_(candidate_ids))).all()

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
        scored.append(
            {
                "memory": m,
                "score": combined,
                "semantic": semantic,
                "keyword": keyword,
                "recency": recency,
                "importance": importance,
                "tokens": count_tokens(m.content) + 4,  # +overhead for a bullet line
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)

    # --- budget-aware selection (greedy pack by relevance, skip items that overflow) ---
    selected, used = [], 0
    for item in scored:
        if used + item["tokens"] <= token_budget:
            selected.append(item)
            used += item["tokens"]

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

    context = "\n".join(f"- {it['memory'].content}" for it in selected)
    return {
        "memories": memories,
        "context": context,
        "tokens_used": used,
        "token_budget": token_budget,
        "candidates_considered": len(scored),
    }
