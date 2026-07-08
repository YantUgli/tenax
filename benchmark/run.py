"""Quantitative benchmark: Tenax hybrid retrieval vs a naive recency baseline.

Both conditions share the same store. The dataset deliberately places the *relevant*
facts in the past and floods the recent window with distractors, so a recency-only
agent (the common "just keep the last N messages" approach) misses them while Tenax's
hybrid + budget-aware recall still surfaces them within the same token budget.

Run (stack must be up + QWEN_API_KEY set):
    pipenv run python -m benchmark.run --reset
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db import session_scope
from app.memory.models import Memory, MemStatus, MemType
from app.memory.retrieve import count_tokens
from app.qwen_client import QwenClient
from benchmark.metrics import retrieval_hit

USER = "benchmark"

# Relevant facts (stored "long ago") each paired with a query and an expected keyword.
QA = [
    ("The user's daughter Mia is severely allergic to peanuts.",
     "What food is unsafe for the user's child?", "peanut"),
    ("The user's production database is PostgreSQL 16 hosted on Alibaba Cloud RDS.",
     "Which database does the user run in production?", "postgres"),
    ("The user prefers being addressed as Dr. Alvarez in formal emails.",
     "How should I address the user in a formal email?", "alvarez"),
    ("The user's startup, Northwind, focuses on supply-chain forecasting.",
     "What does the user's company do?", "supply-chain"),
    ("The user is deploying the Tenax backend to the ap-southeast-1 region.",
     "Which cloud region is the user deploying to?", "ap-southeast-1"),
    ("The user's advisor for the RAG research is Dr. Lin at Tsinghua.",
     "Who is the user's research advisor?", "lin"),
]

DISTRACTORS = [
    "The weather in Paris was sunny on the day of the meeting.",
    "The user watched a documentary about deep-sea creatures.",
    "Lunch today was a chicken sandwich and iced tea.",
    "The office coffee machine was serviced this morning.",
    "A new season of a cooking show was released.",
    "The commute took twenty minutes longer than usual.",
    "The user tried a new keyboard layout for a day.",
    "There was a fire drill in the building.",
    "The user bought a houseplant for the desk.",
    "A colleague recommended a podcast about history.",
]


def _seed(client: QwenClient) -> None:
    now = datetime.now(timezone.utc)
    facts = [q[0] for q in QA]
    fact_vecs = client.embed(facts)
    dist_vecs = client.embed(DISTRACTORS * 3)  # flood the recent window
    with session_scope() as session:
        # relevant facts: old but important
        for (content, _, _), emb in zip(QA, fact_vecs):
            session.add(Memory(
                user_id=USER, content=content, mem_type=MemType.semantic, importance=8.0,
                embedding=emb, created_at=now - timedelta(days=30),
                last_accessed=now - timedelta(days=30), source="seed",
            ))
        # distractors: recent but trivial
        flood = DISTRACTORS * 3
        for i, (content, emb) in enumerate(zip(flood, dist_vecs)):
            session.add(Memory(
                user_id=USER, content=content, mem_type=MemType.episodic, importance=3.0,
                embedding=emb, created_at=now - timedelta(hours=i),
                last_accessed=now - timedelta(hours=i), source="seed",
            ))


def _reset() -> None:
    with session_scope() as session:
        session.execute(delete(Memory).where(Memory.user_id == USER))


def _baseline_recall(session, budget: int) -> str:
    """Naive baseline: most-recent memories packed to the budget (no semantic search)."""
    rows = session.scalars(
        select(Memory)
        .where(Memory.user_id == USER, Memory.status == MemStatus.active)
        .order_by(Memory.created_at.desc())
    ).all()
    picked, used = [], 0
    for m in rows:
        t = count_tokens(m.content) + 4
        if used + t <= budget:
            picked.append(m.content)
            used += t
    return "\n".join(picked), used


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="wipe + reseed the benchmark user")
    ap.add_argument("--budget", type=int, default=400)
    args = ap.parse_args()

    from app.memory.engine import MemoryEngine  # local import: needs DB + key

    client = QwenClient()
    engine = MemoryEngine(client)

    if args.reset:
        _reset()
        _seed(client)
        print(f"Seeded {len(QA)} facts + {len(DISTRACTORS) * 3} distractors for user '{USER}'.\n")

    tenax_hits = base_hits = 0
    tenax_tokens = base_tokens = 0

    print(f"{'query':<48}{'Tenax':>8}{'Baseline':>10}")
    print("-" * 66)
    for _, query, expect in QA:
        res = engine.recall(USER, query, token_budget=args.budget)
        m_ctx, m_tok = res["context"], res["tokens_used"]
        with session_scope() as session:
            b_ctx, b_tok = _baseline_recall(session, args.budget)
        m_ok = retrieval_hit(m_ctx, expect)
        b_ok = retrieval_hit(b_ctx, expect)
        tenax_hits += m_ok
        base_hits += b_ok
        tenax_tokens += m_tok
        base_tokens += b_tok
        print(f"{query[:46]:<48}{'✓' if m_ok else '✗':>8}{'✓' if b_ok else '✗':>10}")

    n = len(QA)
    print("-" * 66)
    print(f"\nRecall@budget={args.budget} tokens")
    print(f"  Tenax (hybrid + budget) : {tenax_hits}/{n}  ({100*tenax_hits/n:.0f}%)  avg {tenax_tokens//n} tok")
    print(f"  Baseline (recency-only) : {base_hits}/{n}  ({100*base_hits/n:.0f}%)  avg {base_tokens//n} tok")


if __name__ == "__main__":
    main()
