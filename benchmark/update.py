"""Langkah 3.1 — knowledge-update benchmark (retrieval form): does belief revision work?

Contradicting facts usually are not similar enough for reflect() to cluster, so without
belief revision they sit side by side and recall serves BOTH the stale and the fresh
belief. This harness proves the write-time revision loop on the gate's criterion #2, in
its free-tier-provable *retrieval form*:

  * update_applied — the stale row is archived with ``superseded_by`` set (DB truth).
  * v2_in          — recall's context contains the new value.
  * v1_out         — recall's context no longer contains the stale STATEMENT. (The new
                     fact may legitimately mention the old value — "left Google, now at
                     Microsoft" — so the check is statement-level, plus a word-level
                     ``stale_keyword`` probe only where the old value cannot leak into
                     the new fact, e.g. an old phone number.)
  * wrong-supersede— trap pairs (distinct entities / complementary attributes / additive
                     preferences) must NOT be superseded. Target: 0 incidents.

Seeding: v1 facts, traps and distractors are inserted directly (deterministic content,
back-dated); the v2 updates go through the REAL write path ``engine.remember(cheap=True)``
so extraction + revision run exactly as in production.

Run (stack up + QWEN_API_KEY set):
    pipenv run python -m benchmark.update
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import session_scope
from app.memory.models import Memory, MemStatus, MemType
from app.memory.retrieve import retrieve
from app.qwen_client import QwenClient
from benchmark.metrics import retrieval_hit

USER = "update-bench"

# (v1 stale fact, v2 update text, query, gold keyword for v2, stale keyword or None)
# gold/stale keywords are concrete specifics (proper nouns, numbers, weekdays) that the
# extractor keeps verbatim; stale_keyword is set only where it cannot appear in v2.
UPDATES: list[tuple[str, str, str, str, str | None]] = [
    ("The user works at Google as a data engineer.",
     "Update: the user left Google and now works at Microsoft.",
     "Where does the user work now?", "microsoft", None),
    ("The user lives in Jakarta.",
     "The user has moved from Jakarta to Singapore.",
     "Which city does the user live in?", "singapore", None),
    ("The user's phone number is 555-0134.",
     "The user's phone number changed; the new number is 555-0199.",
     "What is the user's phone number?", "0199", "0134"),
    ("The user's weekly team sync is on Mondays at 9am.",
     "The weekly team sync has been rescheduled to Thursdays at 2pm.",
     "When is the user's weekly team sync?", "thursday", None),
    ("The user's dissertation advisor is Dr. Chen.",
     "After the department reshuffle, the user's dissertation advisor is now Dr. Park.",
     "Who is the user's dissertation advisor?", "park", None),
    ("The user's favorite programming language is Java.",
     "The user says their favorite programming language is now Rust.",
     "What is the user's favorite programming language?", "rust", None),
]
UPDATE_IMPORTANCE = 8.0

# Traps: the NEW text goes through remember(); the OLD seeded fact must stay active.
# (old fact, new text, query for old fact, old gold keyword, trap kind)
TRAPS: list[tuple[str, str, str, str, str]] = [
    ("The user's daughter Mia is severely allergic to peanuts.",
     "The user's son Leo is severely allergic to shellfish.",
     "What food is unsafe for the user's daughter?", "peanut", "distinct-entity"),
    ("The user drives a blue Tesla Model 3.",
     "The user installed a roof rack on their car last weekend.",
     "What car does the user drive?", "tesla", "complementary-attribute"),
    ("The user drinks coffee every morning.",
     "The user also enjoys green tea in the afternoon.",
     "What does the user drink in the morning?", "coffee", "additive-preference"),
]
TRAP_IMPORTANCE = 7.0

DISTRACTORS = [
    "The weather in Paris was sunny on the day of the meeting.",
    "The user watched a documentary about deep-sea creatures.",
    "Lunch today was a chicken sandwich and iced tea.",
    "The office coffee machine was serviced this morning.",
    "The commute took twenty minutes longer than usual.",
    "A colleague recommended a podcast about history.",
]
DISTRACTOR_IMPORTANCE = 3.0


def _seed(client: QwenClient, base_age_days: float) -> None:
    """Insert v1 facts, trap olds and distractors directly, back-dated."""
    created = datetime.now(timezone.utc) - timedelta(days=base_age_days)
    v1 = [c for c, *_ in UPDATES]
    trap_old = [c for c, *_ in TRAPS]
    texts = v1 + trap_old + DISTRACTORS
    vecs = dict(zip(texts, client.embed(texts)))

    def _add(session, content: str, importance: float, mem_type: MemType) -> None:
        session.add(Memory(
            user_id=USER, content=content, mem_type=mem_type, importance=importance,
            embedding=vecs[content], created_at=created, last_accessed=created,
            source="seed",
        ))

    with session_scope() as session:
        for c in v1:
            _add(session, c, UPDATE_IMPORTANCE, MemType.semantic)
        for c in trap_old:
            _add(session, c, TRAP_IMPORTANCE, MemType.semantic)
        for c in DISTRACTORS:
            _add(session, c, DISTRACTOR_IMPORTANCE, MemType.episodic)


def _row_by_content(content: str) -> dict | None:
    with session_scope() as session:
        m = session.scalars(
            select(Memory).where(Memory.user_id == USER, Memory.content == content)
        ).first()
        return m.as_dict() if m else None


def _recall(client: QwenClient, query: str, budget: int) -> str:
    """Non-reinforcing recall (measurement must not disturb the state)."""
    with session_scope() as session:
        res = retrieve(session, client, USER, query, token_budget=budget, reinforce=False)
    return res["context"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Langkah 3.1 knowledge-update benchmark")
    ap.add_argument("--budget", type=int, default=200,
                    help="recall budget; small so recall stays selective on a micro-corpus")
    ap.add_argument("--base-age-days", type=float, default=30.0,
                    help="how far in the past the stale beliefs were written")
    ap.add_argument("--out", default="benchmark/results/update.jsonl")
    args = ap.parse_args()

    from app.memory.engine import MemoryEngine  # local import: needs DB + key

    client = QwenClient()
    engine = MemoryEngine(client)
    started = time.time()

    engine.purge(USER)
    _seed(client, args.base_age_days)

    records: list[dict] = []

    # --- apply updates through the real write path ---
    print(f"=== updates ({len(UPDATES)}) ===")
    for v1, v2_text, query, gold, stale_kw in UPDATES:
        res = engine.remember(USER, v2_text, cheap=True)
        row = _row_by_content(v1)
        ctx = _recall(client, query, args.budget)

        update_applied = bool(row and row["status"] == "archived" and row["superseded_by"])
        v2_in = retrieval_hit(ctx, gold)
        v1_out = v1.lower() not in ctx.lower()
        value_out = (stale_kw is None) or (stale_kw not in ctx.lower())
        passed = update_applied and v2_in and v1_out and value_out

        rec = {
            "kind": "update", "v1": v1, "gold": gold, "query": query,
            "update_applied": update_applied, "v2_in": v2_in, "v1_out": v1_out,
            "value_out": value_out, "pass": passed,
            "superseded_reported": res["superseded"],
            "context": ctx,
        }
        records.append(rec)
        print(f"  [{'PASS' if passed else 'FAIL'}] {gold:<10} "
              f"applied={update_applied} v2_in={v2_in} v1_out={v1_out} value_out={value_out}")

    # --- traps: these must NOT be superseded ---
    print(f"=== traps ({len(TRAPS)}) ===")
    wrong_supersede = 0
    for old, new_text, query, old_gold, kind in TRAPS:
        engine.remember(USER, new_text, cheap=True)
        row = _row_by_content(old)
        still_active = bool(row and row["status"] == "active" and not row["superseded_by"])
        ctx = _recall(client, query, args.budget)
        old_recallable = retrieval_hit(ctx, old_gold)
        ok = still_active and old_recallable
        if not still_active:
            wrong_supersede += 1
        records.append({
            "kind": "trap", "trap_kind": kind, "old": old, "old_gold": old_gold,
            "still_active": still_active, "old_recallable": old_recallable, "pass": ok,
            "context": ctx,
        })
        print(f"  [{'PASS' if ok else 'FAIL'}] {kind:<24} "
              f"active={still_active} recallable={old_recallable}")

    engine.purge(USER)

    updates = [r for r in records if r["kind"] == "update"]
    traps = [r for r in records if r["kind"] == "trap"]
    n_pass = sum(r["pass"] for r in updates)
    summary = {
        "benchmark": "knowledge-update / belief revision (Langkah 3.1, retrieval form)",
        "measured": datetime.now(timezone.utc).date().isoformat(),
        "n_updates": len(updates),
        "updates_passed": n_pass,
        "update_pass_rate": round(n_pass / len(updates), 4) if updates else None,
        "updates_applied": sum(r["update_applied"] for r in updates),
        "n_traps": len(traps),
        "traps_passed": sum(r["pass"] for r in traps),
        "wrong_supersede_incidents": wrong_supersede,
        "gate2_retrieval_form_pass": (n_pass == len(updates)) and wrong_supersede == 0,
        "config": {"budget": args.budget, "base_age_days": args.base_age_days,
                   "n_distractors": len(DISTRACTORS)},
        "elapsed_sec": round(time.time() - started, 1),
        "usage": client.usage(),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    summary_path = out.with_suffix(".summary.json")
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nupdates: {n_pass}/{len(updates)} pass | wrong-supersede: {wrong_supersede} "
          f"| gate2_retrieval_form_pass = {summary['gate2_retrieval_form_pass']}")
    print(f"Wrote {len(records)} records → {out}\nSummary → {summary_path}")
    u = client.usage()
    print(f"Usage: chat {u['chat_total']} tok / {u['chat_calls']} calls, "
          f"embed {u['embed_total']} tok / {u['embed_calls']} calls")


if __name__ == "__main__":
    main()
