"""Langkah 4 — staleness-resilience benchmark: does self-management corrupt memory?

Standard benchmarks (LongMemEval) never test whether Mnemo's *self-managing* loop
(`forget` decay + `reflect` consolidation) destroys memory as time passes. This harness
does, mapping directly to the Langkah-5 decision gate, criterion #6.

It seeds a synthetic world (important facts + a near-duplicate cluster + a distinct-but-
similar pair + trivial distractors), then runs several cycles of "time passes → forget →
reflect", and after each cycle measures:

  * survival     — do the important facts still surface in recall?
  * wrong-merge  — did reflect conflate two *distinct* facts into one? (target: 0)
  * correct-merge— did the true near-duplicates collapse without losing the answer?
  * storage      — active vs archived counts over time.

Two variants map the boundary: "accessed" (important facts are recalled each cycle, as a
real agent would use them — they MUST survive) and "dormant" (never recalled — this just
characterises the Ebbinghaus decay boundary; fading here is by-design, not a failure).

Time is simulated by *ageing the rows* (shifting timestamps into the past), which composes
correctly with recall's real-clock reinforcement — rather than by a simulated sweep clock.

Run (stack up + QWEN_API_KEY set):
    pipenv run python -m benchmark.staleness --cycles 3 --delta-days 14 --variant both
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, update

from app.db import session_scope
from app.memory.models import Memory, MemStatus, MemType
from app.memory.retrieve import retrieve
from app.qwen_client import QwenClient
from benchmark.metrics import retrieval_hit

USER = "staleness-bench"

# Important facts the agent cares about — each with a query + a gold keyword. These must
# survive the forget/reflect loop when they are actively used (the "accessed" variant).
# Mia/peanut and Leo/shellfish are also the distinct-but-similar pair (see WRONG_MERGE).
IMPORTANT: list[tuple[str, str, str]] = [
    ("The user's daughter Mia is severely allergic to peanuts.",
     "What food is unsafe for the user's daughter?", "peanut"),
    ("The user's son Leo is severely allergic to shellfish.",
     "What food is unsafe for the user's son?", "shellfish"),
    ("The user prefers being addressed as Dr. Alvarez in formal emails.",
     "How should I address the user in a formal email?", "alvarez"),
    ("The user's startup, Northwind, focuses on supply-chain forecasting.",
     "What does the user's company do?", "supply-chain"),
    ("The user is deploying the Mnemo backend to the ap-southeast-1 region.",
     "Which cloud region is the user deploying to?", "ap-southeast-1"),
    ("The user's advisor for the RAG research is Dr. Lin at Tsinghua.",
     "Who is the user's research advisor?", "lin"),
]
IMPORTANT_IMPORTANCE = 8.0

# A single fact stated three ways — reflect SHOULD merge these into one canonical memory
# without losing the answer ("monday"). Its query is included in the accessed set.
NEAR_DUP_VARIANTS = [
    "The user's weekly team sync is on Mondays at 9am.",
    "The user holds a team standup every Monday at 9 in the morning.",
    "Weekly, the user meets the team for a sync each Monday 9am.",
]
NEAR_DUP_QUERY = "When is the user's weekly team sync?"
NEAR_DUP_KEYWORD = "monday"
NEAR_DUP_IMPORTANCE = 7.0

# reflect must NOT conflate these distinct entities. Checked two ways: (a) both gold
# keywords still recall, (b) no single active memory mentions both entities/allergens.
WRONG_MERGE_ENTITIES = ("mia", "leo")
WRONG_MERGE_ALLERGENS = ("peanut", "shellfish")

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
DISTRACTOR_IMPORTANCE = 3.0

# Accessed queries: the important facts + the near-dup topic (facts an agent actually uses).
ACCESSED_QUERIES = [(q, kw) for _, q, kw in IMPORTANT] + [(NEAR_DUP_QUERY, NEAR_DUP_KEYWORD)]


def _seed(client: QwenClient, base_age_days: float) -> None:
    """Insert the synthetic world, back-dated by ``base_age_days`` so decay is meaningful."""
    now = datetime.now(timezone.utc)
    created = now - timedelta(days=base_age_days)

    important = [c for c, _, _ in IMPORTANT]
    all_texts = important + NEAR_DUP_VARIANTS + DISTRACTORS
    vecs = client.embed(all_texts)
    by_text = dict(zip(all_texts, vecs))

    with session_scope() as session:
        for content in important:
            session.add(Memory(
                user_id=USER, content=content, mem_type=MemType.semantic,
                importance=IMPORTANT_IMPORTANCE, embedding=by_text[content],
                created_at=created, last_accessed=created, source="seed",
            ))
        for content in NEAR_DUP_VARIANTS:
            session.add(Memory(
                user_id=USER, content=content, mem_type=MemType.semantic,
                importance=NEAR_DUP_IMPORTANCE, embedding=by_text[content],
                created_at=created, last_accessed=created, source="seed",
            ))
        for content in DISTRACTORS:
            session.add(Memory(
                user_id=USER, content=content, mem_type=MemType.episodic,
                importance=DISTRACTOR_IMPORTANCE, embedding=by_text[content],
                created_at=created, last_accessed=created, source="seed",
            ))


def _age_world(delta_days: float) -> None:
    """Shift every active memory ``delta_days`` into the past — simulate time elapsing."""
    d = timedelta(days=delta_days)
    with session_scope() as session:
        session.execute(
            update(Memory)
            .where(Memory.user_id == USER, Memory.status == MemStatus.active)
            .values(created_at=Memory.created_at - d, last_accessed=Memory.last_accessed - d)
        )


def _recall(client: QwenClient, query: str, budget: int, *, reinforce: bool) -> str:
    """Return the recalled context. ``reinforce=False`` for measurement (no access bump)."""
    with session_scope() as session:
        res = retrieve(session, client, USER, query, token_budget=budget, reinforce=reinforce)
    return res["context"]


def _active_contents() -> list[str]:
    with session_scope() as session:
        rows = session.scalars(
            select(Memory.content).where(
                Memory.user_id == USER, Memory.status == MemStatus.active
            )
        ).all()
    return list(rows)


def _counts() -> dict:
    with session_scope() as session:
        by_status = dict(
            session.execute(
                select(Memory.status, func.count())
                .where(Memory.user_id == USER)
                .group_by(Memory.status)
            ).all()
        )
    return {k.value: v for k, v in by_status.items()}


def _measure(client: QwenClient, budget: int) -> dict:
    """Non-reinforcing measurement of survival + wrong-merge on the current active set."""
    survived = 0
    misses = []
    for content, query, keyword in IMPORTANT:
        ctx = _recall(client, query, budget, reinforce=False)
        if retrieval_hit(ctx, keyword):
            survived += 1
        else:
            misses.append(keyword)

    near_dup_ctx = _recall(client, NEAR_DUP_QUERY, budget, reinforce=False)
    near_dup_hit = retrieval_hit(near_dup_ctx, NEAR_DUP_KEYWORD)

    # wrong-merge: any single active memory that conflates the two distinct people/allergens
    active = [c.lower() for c in _active_contents()]
    conflated = [
        c for c in active
        if (all(e in c for e in WRONG_MERGE_ENTITIES)
            or all(a in c for a in WRONG_MERGE_ALLERGENS))
    ]
    both_allergens_recallable = (
        retrieval_hit(_recall(client, IMPORTANT[0][1], budget, reinforce=False), "peanut")
        and retrieval_hit(_recall(client, IMPORTANT[1][1], budget, reinforce=False), "shellfish")
    )

    return {
        "survived": survived,
        "important_total": len(IMPORTANT),
        "survival_rate": round(survived / len(IMPORTANT), 4),
        "survival_misses": misses,
        "near_dup_answer_hit": near_dup_hit,
        "wrong_merge_incidents": len(conflated),
        "wrong_merge_examples": conflated[:3],
        "distinct_pair_both_recallable": both_allergens_recallable,
        "counts": _counts(),
    }


def run_variant(client, engine, variant: str, *, cycles: int, delta_days: float,
                base_age_days: float, budget: int) -> dict:
    """Run one experiment (accessed|dormant) end to end; return records + summary."""
    engine.purge(USER)
    _seed(client, base_age_days)

    records = []
    reflect_totals = {"clusters_found": 0, "memories_merged": 0, "semantic_created": 0}

    baseline = _measure(client, budget)
    baseline.update({"variant": variant, "cycle": 0, "phase": "baseline"})
    records.append(baseline)

    for cyc in range(1, cycles + 1):
        # 1) realistic access: an agent recalling the facts it uses (accessed variant only)
        if variant == "accessed":
            for query, _ in ACCESSED_QUERIES:
                _recall(client, query, budget, reinforce=True)
        # 2) time passes
        _age_world(delta_days)
        # 3) self-management
        forget_res = engine.forget(USER)
        reflect_res = engine.reflect(USER, cheap=True)
        for k in reflect_totals:
            reflect_totals[k] += reflect_res.get(k, 0)
        # 4) measure (non-reinforcing)
        m = _measure(client, budget)
        m.update({
            "variant": variant, "cycle": cyc, "phase": "post_cycle",
            "forget": forget_res,
            "reflect": reflect_res,
        })
        records.append(m)

    final = records[-1]
    summary = {
        "variant": variant,
        "cycles": cycles,
        "delta_days": delta_days,
        "final_survival_rate": final["survival_rate"],
        "final_survived": final["survived"],
        "important_total": len(IMPORTANT),
        "total_wrong_merge_incidents": sum(r["wrong_merge_incidents"] for r in records),
        "distinct_pair_preserved": all(r["distinct_pair_both_recallable"] for r in records),
        "correct_merge_happened": reflect_totals["memories_merged"] >= 2,
        "near_dup_answer_survived": final["near_dup_answer_hit"],
        "reflect_totals": reflect_totals,
        "final_counts": final["counts"],
    }
    return {"records": records, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description="Langkah 4 staleness-resilience benchmark")
    ap.add_argument("--cycles", type=int, default=3)
    ap.add_argument("--delta-days", type=float, default=14.0)
    ap.add_argument("--base-age-days", type=float, default=1.0,
                    help="initial age of seeds before the first cycle")
    # Small on purpose: budget-aware recall should be *selective*. On this ~20-memory
    # micro-corpus a 1200-token budget would surface (and reinforce) everything, masking
    # forget's job. ~150 tokens surfaces only the most relevant handful — the realistic
    # slice — so unrelated distractors stay unreinforced and are allowed to decay.
    ap.add_argument("--budget", type=int, default=150)
    ap.add_argument("--variant", choices=["accessed", "dormant", "both"], default="both")
    ap.add_argument("--out", default="benchmark/results/staleness.jsonl")
    args = ap.parse_args()

    from app.memory.engine import MemoryEngine  # local import: needs DB + key

    client = QwenClient()
    engine = MemoryEngine(client)

    variants = ["accessed", "dormant"] if args.variant == "both" else [args.variant]
    started = time.time()
    all_records: list[dict] = []
    variant_summaries: dict[str, dict] = {}

    for v in variants:
        print(f"\n=== variant: {v} (cycles={args.cycles}, Δ={args.delta_days}d) ===")
        res = run_variant(
            client, engine, v,
            cycles=args.cycles, delta_days=args.delta_days,
            base_age_days=args.base_age_days, budget=args.budget,
        )
        all_records.extend(res["records"])
        variant_summaries[v] = res["summary"]
        s = res["summary"]
        for r in res["records"]:
            tag = "baseline" if r["cycle"] == 0 else f"cycle {r['cycle']}"
            print(f"  {tag:>9}: survival {r['survived']}/{r['important_total']} "
                  f"({100*r['survival_rate']:.0f}%)  wrong-merge {r['wrong_merge_incidents']}  "
                  f"active={r['counts'].get('active', 0)} archived={r['counts'].get('archived', 0)}")
        print(f"  → final survival {100*s['final_survival_rate']:.0f}%, "
              f"wrong-merge total {s['total_wrong_merge_incidents']}, "
              f"correct-merge {'yes' if s['correct_merge_happened'] else 'no'}, "
              f"near-dup answer survived {'yes' if s['near_dup_answer_survived'] else 'no'}")

    # engine.purge leaves the namespace clean for the next run
    engine.purge(USER)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    # gate #6 verdict: pass iff the accessed variant keeps every important fact AND nothing
    # was ever wrongly merged across any variant/cycle.
    # distinct_pair_preserved is only meaningful where the pair is kept alive (accessed);
    # the dormant variant lets both decay by design, so it must not count against the gate.
    # "reflect never conflated them" is already proven by wrong_merge_incidents == 0 (all).
    accessed = variant_summaries.get("accessed")
    gate6_pass = None
    if accessed is not None:
        gate6_pass = (
            accessed["final_survival_rate"] == 1.0
            and all(vs["total_wrong_merge_incidents"] == 0 for vs in variant_summaries.values())
            and accessed["distinct_pair_preserved"]
        )

    summary = {
        "benchmark": "staleness-resilience (Langkah 4)",
        "gate6_pass": gate6_pass,
        "variants": variant_summaries,
        "elapsed_sec": round(time.time() - started, 1),
        "usage": client.usage(),
        "config": {
            "cycles": args.cycles,
            "delta_days": args.delta_days,
            "base_age_days": args.base_age_days,
            "budget": args.budget,
            "variant": args.variant,
            "n_important": len(IMPORTANT),
            "n_near_dup": len(NEAR_DUP_VARIANTS),
            "n_distractors": len(DISTRACTORS),
        },
    }
    summary_path = out.with_suffix(".summary.json")
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {len(all_records)} records → {out}")
    print(f"Summary → {summary_path}")
    print(f"gate6_pass = {gate6_pass}")
    u = client.usage()
    print(f"Usage: chat {u['chat_total']} tok / {u['chat_calls']} calls, "
          f"embed {u['embed_total']} tok / {u['embed_calls']} calls")


if __name__ == "__main__":
    main()
