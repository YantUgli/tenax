"""Mechanism B diagnostic: why did a multi-fact question lose its bridging fact?

Runs against an already-ingested bench namespace (a `--keep-users` run), so it costs
one query embedding per item and no reader/judge calls at all.

For each item it separates the three candidate causes:
  (c) NOT EXTRACTED  - no memory from the gold evidence session exists at all
                       -> a WRITE-path problem (breaks the cheap --skip-ingest plan)
  (b) NOT A CANDIDATE - the gold memory exists but never entered the candidate set
                       -> candidate generation (query decomposition / higher k)
  (a) LOST THE BUDGET - it was a candidate but ranked below the packing cut
                       -> ranking / diversity-aware packing (MMR)

Usage:
  <venv-python> -m benchmark.coverage_diag --ids gpt4_7f6b06db,gpt4_45189cb4
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from sqlalchemy import select

from app.db import session_scope
from app.memory.models import Memory
from app.memory.retrieve import _VISIBLE, count_tokens
from app.qwen_client import QwenClient


def load_items(dataset: str, ids: set[str]) -> list[dict]:
    with open(dataset, encoding="utf-8") as fh:
        data = json.load(fh)
    return [it for it in data if it.get("question_id") in ids]


def diagnose(item: dict, client: QwenClient, *, budget: int, candidate_k: int) -> None:
    qid = item["question_id"]
    question = item.get("question", "")
    gold_sessions = set(item.get("answer_session_ids") or [])
    user_id = f"bench:{qid}"

    print("=" * 78)
    print(f"{qid}  |  {question}")
    print(f"gold answer: {item.get('answer')}")
    print(f"gold evidence sessions: {sorted(gold_sessions)}")

    qvec = np.asarray(client.embed_one(question), dtype=np.float32)

    with session_scope() as session:
        # every memory extracted from a gold evidence session
        gold_rows = session.scalars(
            select(Memory).where(Memory.user_id == user_id, Memory.source.in_(gold_sessions))
        ).all()
        if not gold_rows:
            print("\n  (c) NOT EXTRACTED - no memory exists from any gold session. WRITE-path gap.")
            return

        # candidate set exactly as retrieve() builds it (dense half; the ANN order is what
        # decides whether a memory is even considered)
        cand_ids = set(
            session.scalars(
                select(Memory.id)
                .where(Memory.user_id == user_id, _VISIBLE)
                .order_by(Memory.embedding.cosine_distance(qvec.tolist()))
                .limit(candidate_k)
            ).all()
        )

        total = session.scalar(
            select(Memory.id).where(Memory.user_id == user_id).order_by(Memory.id.desc()).limit(1)
        )
        print(f"\n  gold-session memories stored: {len(gold_rows)}  (corpus high-water id {total})")

        rows = []
        for m in gold_rows:
            emb = np.asarray(m.embedding, dtype=np.float32)
            denom = (np.linalg.norm(qvec) * np.linalg.norm(emb)) or 1e-9
            cos = float(np.dot(qvec, emb) / denom)
            rows.append((cos, m.id in cand_ids, m))
        rows.sort(key=lambda r: -r[0])

        in_cand = sum(1 for c, isc, _ in rows if isc)
        print(f"  of those, entered candidate set (k={candidate_k}): {in_cand}/{len(rows)}")

        print(f"\n  {'cos':>6}  {'cand':>5}  {'tok':>4}  content")
        for cos, is_cand, m in rows[:12]:
            mark = "yes" if is_cand else "NO"
            print(f"  {cos:6.3f}  {mark:>5}  {count_tokens(m.content):4d}  {m.content[:88]}")

        if in_cand == 0:
            print("\n  => (b) NOT A CANDIDATE: gold facts exist but lose the ANN cut.")
        elif in_cand < len(rows):
            print("\n  => mixed (a)/(b): some gold facts are candidates, others miss the ANN cut.")
        else:
            print("\n  => (a) LOST THE BUDGET: all gold facts are candidates; packing dropped them.")
        print(f"     (budget {budget} tok; competing against the rest of the candidate set)")


def main() -> None:
    p = argparse.ArgumentParser(description="Mechanism B coverage diagnostic")
    p.add_argument("--dataset", default="data/longmemeval_s.json")
    p.add_argument("--ids", required=True, help="comma-separated question_ids")
    p.add_argument("--budget", type=int, default=1200)
    p.add_argument("--candidate-k", type=int, default=50)
    args = p.parse_args()

    ids = {s.strip() for s in args.ids.split(",") if s.strip()}
    items = load_items(args.dataset, ids)
    if not items:
        print("no matching items in dataset")
        return
    client = QwenClient()
    for it in items:
        diagnose(it, client, budget=args.budget, candidate_k=args.candidate_k)


if __name__ == "__main__":
    main()
