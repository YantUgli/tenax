"""LongMemEval harness for Tenax — the load-bearing benchmark of Langkah 1.

LongMemEval (Wu et al., 2024) is 500 questions, each with its own multi-session chat
history ("haystack") carrying per-session timestamps. It explicitly probes *knowledge
update* and *temporal reasoning* — the two weakest spots of any long-term memory core —
which is why it is the primary gate for deciding whether to extend Tenax into grounded.

Pipeline per question (mirrors the protocol):

    ingest  → for each session (chronological): engine.remember(user, text,
              source=session_id, event_time=session_date)   [Langkah 0 hooks]
    recall  → engine.recall(user, question, token_budget=B) → context
    read    → Qwen answers using ONLY the context (+ question_date)
    judge   → LongMemEval's own LLM-as-judge prompt → correct / wrong
    record  → overall acc, per-category acc, retrieval hit-rate, tokens/query

Each question is isolated under a unique user_id (``bench:{question_id}``) and purged
before ingest, so no facts leak between questions.

Getting the data (you provide the file; the harness never downloads):
    LongMemEval-S (~115k tok/q) is the target. Grab ``longmemeval_s.json`` from the
    official release (GitHub xiaowu0162/LongMemEval or its HuggingFace mirror) and pass
    it via --dataset.

Usage:
    # free sanity check — just parses the file and prints category counts
    pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_s.json --dry-run

    # cheap partial retrieval baseline (no reader/judge cost): retrieval hit-rate + tokens
    pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_s.json \
        --limit 20 --retrieval-only

    # full end-to-end baseline
    pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_s.json \
        --out benchmark/results/baseline.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from benchmark.metrics import retrieval_hit

# Free-tier ceiling per model (DashScope): used only for --estimate / usage warnings.
QUOTA_LIMIT = 1_000_000
QUOTA_WARN = 900_000

# ----------------------------------------------------------------------------- dataset

_CATEGORIES = (
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "temporal-reasoning",
    "knowledge-update",
    "abstention",
)

_DATE_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def load_dataset(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list of questions, got {type(data).__name__}")
    return data


def parse_dt(raw: str | None) -> datetime | None:
    """Parse a LongMemEval timestamp (e.g. '2023/05/20 (Sat) 02:21') to tz-aware UTC.

    Returns None if unparseable so the caller can fall back to now() rather than crash.
    """
    if not raw:
        return None
    cleaned = re.sub(r"\([^)]*\)", " ", str(raw))          # drop weekday like "(Sat)"
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_abstention(item: dict) -> bool:
    """Abstention questions are flagged by an ``_abs`` suffix on the question_id."""
    return str(item.get("question_id", "")).endswith("_abs")


def category_of(item: dict) -> str:
    return "abstention" if is_abstention(item) else str(item.get("question_type", "unknown"))


def iter_sessions(item: dict):
    """Yield (session_id, session_dt, turns) for a question, chronological by date.

    Sessions with an unparseable date sort last but keep their original relative order.
    """
    sessions = item.get("haystack_sessions") or []
    ids = item.get("haystack_session_ids") or [f"sess{i}" for i in range(len(sessions))]
    dates = item.get("haystack_dates") or [None] * len(sessions)

    triples = []
    for idx, (sid, sdate, turns) in enumerate(zip(ids, dates, sessions)):
        triples.append((idx, sid, parse_dt(sdate), turns))

    # chronological; None dates go to the end but preserve input order via idx
    triples.sort(key=lambda t: (t[2] is None, t[2] or datetime.min.replace(tzinfo=timezone.utc), t[0]))
    for _, sid, sdt, turns in triples:
        yield sid, sdt, turns


def session_text(turns: list[dict]) -> str:
    """Render a session's turns as a labelled transcript so the extractor sees who said what.

    Both roles are kept: single-session-assistant questions need facts the assistant stated.
    """
    lines = []
    for t in turns or []:
        role = str(t.get("role", "user")).capitalize()
        content = (t.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def iter_sessions_capped(item: dict, max_sessions: int):
    """Like ``iter_sessions`` but cap total sessions to ``max_sessions``.

    All *evidence* sessions (``answer_session_ids``) are always kept — dropping gold would
    make the question unanswerable — then the earliest non-evidence sessions fill the
    remaining slots. The kept set is returned in chronological order so ``event_time``
    stays correct. This is the lever that bounds tokens/question for the free tier; if the
    evidence sessions alone exceed the cap, all of them are still kept.
    """
    sessions = list(iter_sessions(item))  # already chronological, undated last
    if not max_sessions or max_sessions <= 0 or len(sessions) <= max_sessions:
        return sessions

    evidence = set(item.get("answer_session_ids") or [])
    ev = [s for s in sessions if s[0] in evidence]
    non = [s for s in sessions if s[0] not in evidence]
    slots = max(max_sessions - len(ev), 0)
    keep = ev + non[:slots]
    keep.sort(key=lambda t: (t[1] is None, t[1] or datetime.min.replace(tzinfo=timezone.utc)))
    return keep


# --------------------------------------------------------------------------- selection

def stratified_sample(items: list[dict], n: int, seed: int) -> list[dict]:
    """Pick ``n`` items proportionally across the 7 categories (deterministic by ``seed``).

    The dataset file is grouped by category, so a plain ``--limit`` would draw from a
    single category. Proportional (largest-remainder) allocation keeps every category
    represented so per-category accuracy stays meaningful on a small sample.
    """
    if not n or n >= len(items):
        return items
    rng = random.Random(seed)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_cat[category_of(it)].append(it)
    cats = sorted(by_cat)
    total = len(items)

    quota = {c: n * len(by_cat[c]) / total for c in cats}
    alloc = {c: int(quota[c]) for c in cats}
    remainder = n - sum(alloc.values())
    for c in sorted(cats, key=lambda c: quota[c] - alloc[c], reverse=True)[:remainder]:
        alloc[c] += 1

    picked: list[dict] = []
    for c in cats:
        pool = by_cat[c][:]
        rng.shuffle(pool)
        picked.extend(pool[: min(alloc[c], len(pool))])
    return picked


def select_items(items: list[dict], args) -> list[dict]:
    """Apply category filter, then either stratified --sample or --offset/--limit, then --shuffle.

    When ``--sample`` is given it supersedes ``--offset``/``--limit`` (sampling defines the
    set). ``--shuffle`` only reorders — useful to decorrelate item order from category when
    extraction-model rotation is on.
    """
    if args.categories:
        wanted = {c.strip() for c in args.categories.split(",")}
        items = [it for it in items if category_of(it) in wanted]

    if getattr(args, "ids", None):
        # exact-item re-runs (e.g. before/after a targeted fix on the same questions)
        wanted_ids = {i.strip() for i in args.ids.split(",") if i.strip()}
        items = [it for it in items if it["question_id"] in wanted_ids]
        return items

    if getattr(args, "sample", 0):
        items = stratified_sample(items, args.sample, args.seed)
    else:
        items = items[args.offset : args.offset + args.limit] if args.limit else items[args.offset :]

    if getattr(args, "shuffle", False):
        items = items[:]
        random.Random(args.seed).shuffle(items)
    return items


# ------------------------------------------------------------------------------- reader

_READER_SYSTEM = (
    "You are a helpful personal assistant with access to the user's long-term memory. "
    "Answer the user's question using ONLY the facts in the provided MEMORY CONTEXT. "
    "Do not use outside knowledge or make assumptions beyond the context.\n"
    "How to read the context:\n"
    "- Each memory line starts with [YYYY-MM-DD]: the date the fact happened or became true "
    "(already resolved to an absolute date). Treat this as the event's own date and use it "
    "together with the Current date for any ordering, duration, or 'how long ago' arithmetic. "
    "If a line still contains a relative expression, prefer the bracketed date.\n"
    "- Lines marked 'PAST (superseded on <date>)' are earlier values that were later "
    "replaced. Use them for questions about what was true BEFORE or ORIGINALLY; use the "
    "unmarked lines for the current state.\n"
    "How to answer:\n"
    "- For questions about time, order, or duration: first list the relevant dated facts in "
    "chronological order, then compute the ordering/duration/count step by step, then state "
    "the final answer.\n"
    "- For questions asking a total or count across multiple events: enumerate every "
    "matching fact explicitly, then sum them.\n"
    "- For questions asking for suggestions or recommendations: give a personalized "
    "suggestion grounded in the user's stated preferences and past experiences, rather than "
    "just restating facts.\n"
    "- If the context genuinely does not contain the information needed, say clearly that "
    "you don't know or that the information is not available.\n"
    "Show your brief reasoning first, then give a clear final answer."
)


def read_answer(client, question: str, context: str, question_date: str | None, *, cheap: bool) -> str:
    user = (
        f"Current date: {question_date or 'unknown'}\n\n"
        f"MEMORY CONTEXT:\n{context or '(no relevant memories retrieved)'}\n\n"
        f"QUESTION: {question}"
    )
    return client.chat(
        [{"role": "system", "content": _READER_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.0,
        cheap=cheap,
    ).strip()


# -------------------------------------------------------------------------------- judge

def judge_prompt(item: dict, response: str) -> str:
    """Reproduce LongMemEval's official `get_anscheck_prompt` (metric-specific)."""
    q = item.get("question", "")
    a = item.get("answer", "")
    task = str(item.get("question_type", ""))

    if is_abstention(item):
        return (
            "I will give you an unanswerable question, an explanation, and a response from "
            "a model. Please answer yes if the model correctly identifies the question as "
            "unanswerable. The model could say that the information is incomplete, or some "
            "other information is given but the asked information is not.\n\n"
            f"Question: {q}\nExplanation: {a}\nModel Response: {response}\n\n"
            "Does the model correctly identify the question as unanswerable? "
            "Answer yes or no only."
        )
    if task == "temporal-reasoning":
        return (
            "I will give you a question, a correct answer, and a response from a model. "
            "Please answer yes if the response contains the correct answer. Otherwise, "
            "answer no. If the response is equivalent to the correct answer or contains all "
            "the intermediate steps to get the correct answer, you should also answer yes. "
            "If the response only contains a subset of the information required by the "
            "answer, answer no. In addition, do not penalize off-by-one errors for the "
            "number of days. If the question asks for the number of days/weeks/months, etc., "
            "and the model makes off-by-one errors (e.g., predicting 19 days when the answer "
            "is 20 days), the model's response is still correct.\n\n"
            f"Question: {q}\nCorrect Answer: {a}\nModel Response: {response}\n\n"
            "Is the model response correct? Answer yes or no only."
        )
    if task == "knowledge-update":
        return (
            "I will give you a question, a correct answer, and a response from a model. "
            "Please answer yes if the response contains the correct answer. Otherwise, "
            "answer no. If the response contains some previous information along with an "
            "updated answer, the response should be considered as correct as long as the "
            "updated answer is the required answer.\n\n"
            f"Question: {q}\nCorrect Answer: {a}\nModel Response: {response}\n\n"
            "Is the model response correct? Answer yes or no only."
        )
    if task == "single-session-preference":
        return (
            "I will give you a question, a rubric for desired personalized response, and a "
            "response from a model. Please answer yes if the response satisfies the desired "
            "response. Otherwise, answer no. The rubric may contain multiple items, and the "
            "response should satisfy all of the items to be considered correct.\n\n"
            f"Question: {q}\nRubric: {a}\nModel Response: {response}\n\n"
            "Is the model response correct? Answer yes or no only."
        )
    return (
        "I will give you a question, a correct answer, and a response from a model. Please "
        "answer yes if the response contains the correct answer. Otherwise, answer no. If "
        "the response is equivalent to the correct answer or contains all the intermediate "
        "steps to get the correct answer, you should also answer yes. If the response only "
        "contains a subset of the information required by the answer, answer no.\n\n"
        f"Question: {q}\nCorrect Answer: {a}\nModel Response: {response}\n\n"
        "Is the model response correct? Answer yes or no only."
    )


def judge(client, item: dict, response: str, *, model: str | None) -> bool:
    verdict = client.chat(
        [{"role": "user", "content": judge_prompt(item, response)}],
        temperature=0.0,
        model=model,
    )
    return verdict.strip().lower().startswith("yes")


# ---------------------------------------------------------------------------- per-item

def ingest_item(engine, item: dict, *, granularity: str, cheap: bool, max_sessions: int = 0) -> int:
    """Replay a question's haystack into its isolated namespace. Returns sessions ingested."""
    user_id = f"bench:{item['question_id']}"
    engine.purge(user_id)
    n = 0
    for sid, sdt, turns in iter_sessions_capped(item, max_sessions):
        if granularity == "turn":
            for t in turns or []:
                content = (t.get("content") or "").strip()
                if not content:
                    continue
                role = str(t.get("role", "user")).capitalize()
                engine.remember(user_id, f"{role}: {content}", source=sid, event_time=sdt, cheap=cheap)
        else:  # session
            text = session_text(turns)
            if text:
                engine.remember(user_id, text, source=sid, event_time=sdt, cheap=cheap)
        n += 1
        print(f"    ingest {item['question_id']}: session {n}", end="\r", flush=True)
    if n:
        print()  # newline so the next line doesn't overwrite this progress
    return n


def recency_recall(user_id: str, budget: int) -> tuple[str, int, int]:
    """Naive baseline recall: most-recent active memories packed to ``budget`` (no search).

    Mirrors ``benchmark/run.py``'s ``_baseline_recall`` — the "just keep the last N" strawman
    Tenax's hybrid recall is measured against (criterion #1). Returns (context, tokens, count).
    """
    from sqlalchemy import select

    from app.db import session_scope
    from app.memory.models import Memory, MemStatus
    from app.memory.retrieve import count_tokens

    with session_scope() as session:
        rows = session.scalars(
            select(Memory)
            .where(Memory.user_id == user_id, Memory.status == MemStatus.active)
            .order_by(Memory.created_at.desc())
        ).all()
        picked, used = [], 0
        for m in rows:
            t = count_tokens(m.content) + 4
            if used + t <= budget:
                picked.append(m.content)
                used += t
    return "\n".join(f"- {c}" for c in picked), used, len(picked)


def eval_item(engine, client, item: dict, args) -> dict:
    user_id = f"bench:{item['question_id']}"
    question = item.get("question", "")

    baseline = getattr(args, "baseline", "none")
    evidence = set(item.get("answer_session_ids") or [])
    if baseline == "recency":
        # naive strawman: no semantic search, no per-memory source → retrieval hits N/A
        context, tokens_used, n_memories = recency_recall(user_id, args.budget)
        recalled_sources: set[str] = set()
        hit_evidence = None
        coverage = None
    else:
        rec = engine.recall(user_id, question, token_budget=args.budget, candidate_k=args.candidate_k)
        context = rec.get("context", "")
        memories = rec.get("memories", [])
        tokens_used = rec.get("tokens_used", 0)
        n_memories = len(memories)
        recalled_sources = {m.get("source") for m in memories if m.get("source")}
        # retrieval hit = a recalled memory came from a gold evidence session
        hit_evidence = bool(recalled_sources & evidence) if evidence else None
        # coverage = EVERY gold evidence session is represented. hit_evidence only needs
        # one, so it reads 100% even when a multi-fact question is missing the second fact
        # it needs; coverage is the metric that actually moves with budget packing.
        coverage = evidence.issubset(recalled_sources) if evidence else None

    # secondary, informational: does the gold answer string surface in context?
    hit_answer = None if is_abstention(item) else retrieval_hit(context, item.get("answer", ""))

    record = {
        "question_id": item.get("question_id"),
        "category": category_of(item),
        "is_abstention": is_abstention(item),
        "question": question,
        "gold": item.get("answer"),
        "baseline": baseline,
        "tokens_used": tokens_used,
        "n_memories": n_memories,
        "recalled_sources": sorted(s for s in recalled_sources if s),
        "answer_session_ids": sorted(evidence),
        "retrieval_hit_evidence": hit_evidence,
        "retrieval_coverage": coverage,
        "retrieval_hit_answer": hit_answer,
    }

    if not args.retrieval_only:
        response = read_answer(client, question, context, item.get("question_date"), cheap=args.cheap)
        correct = judge(client, item, response, model=args.judge_model)
        record["response"] = response
        record["correct"] = correct
    return record


# ------------------------------------------------------------------------------ report

def summarize(records: list[dict], *, retrieval_only: bool) -> dict:
    by_cat_total: dict[str, int] = defaultdict(int)
    by_cat_correct: dict[str, int] = defaultdict(int)
    hit_num = hit_den = 0
    cov_num = cov_den = 0
    tokens = []

    for r in records:
        cat = r["category"]
        by_cat_total[cat] += 1
        if not retrieval_only and r.get("correct"):
            by_cat_correct[cat] += 1
        if r.get("retrieval_hit_evidence") is not None:
            hit_den += 1
            hit_num += 1 if r["retrieval_hit_evidence"] else 0
        if r.get("retrieval_coverage") is not None:
            cov_den += 1
            cov_num += 1 if r["retrieval_coverage"] else 0
        tokens.append(r.get("tokens_used", 0))

    total = len(records)
    overall_correct = sum(by_cat_correct.values())
    return {
        "n_items": total,
        "overall_accuracy": (overall_correct / total) if (total and not retrieval_only) else None,
        "per_category": {
            cat: {
                "n": by_cat_total[cat],
                "accuracy": (by_cat_correct[cat] / by_cat_total[cat]) if (by_cat_total[cat] and not retrieval_only) else None,
            }
            for cat in sorted(by_cat_total)
        },
        "retrieval_hit_rate": (hit_num / hit_den) if hit_den else None,
        "retrieval_hit_scored": hit_den,
        "retrieval_coverage_rate": (cov_num / cov_den) if cov_den else None,
        "retrieval_coverage_scored": cov_den,
        "avg_tokens_per_query": (sum(tokens) / len(tokens)) if tokens else 0,
    }


def _pct(x) -> str:
    return "  n/a " if x is None else f"{100 * x:5.1f}%"


def print_summary(summary: dict, *, retrieval_only: bool) -> None:
    print("\n" + "=" * 60)
    print("LongMemEval — Tenax" + ("  [retrieval-only]" if retrieval_only else ""))
    print("=" * 60)
    print(f"Items scored               : {summary['n_items']}")
    if not retrieval_only:
        print(f"Overall accuracy           : {_pct(summary['overall_accuracy'])}")
    print(f"Retrieval hit-rate (evid.) : {_pct(summary['retrieval_hit_rate'])}"
          f"   (over {summary['retrieval_hit_scored']} items with gold sessions)")
    print(f"Retrieval coverage (ALL)   : {_pct(summary.get('retrieval_coverage_rate'))}"
          f"   (every gold session represented)")
    print(f"Avg tokens / query         : {summary['avg_tokens_per_query']:.0f}")
    print("-" * 60)
    print(f"{'category':<28}{'n':>4}{'accuracy':>12}")
    print("-" * 60)
    for cat, v in summary["per_category"].items():
        print(f"{cat:<28}{v['n']:>4}{_pct(v['accuracy']):>12}")
    print("=" * 60)


# ---------------------------------------------------------------------------- estimate

def estimate(items: list[dict], args) -> dict:
    """Project chat & embed token cost vs. the 1M free-tier ceiling — read-only, no API.

    Approximations are deliberately conservative (they over-estimate): embedding cost uses
    the *raw* session text as a proxy for the (shorter) extracted facts, and extraction
    completion is a fraction of the input. If this says a config fits under 1M, the real
    run should too.
    """
    from app.memory.extract import _SYSTEM as EXTRACT_SYSTEM
    from app.memory.retrieve import count_tokens

    extract_sys = count_tokens(EXTRACT_SYSTEM)
    reader_sys = count_tokens(_READER_SYSTEM)

    chat_prompt = chat_completion = embed_prompt = 0
    chat_calls = embed_calls = 0
    total_sessions = 0

    for it in items:
        # --- ingest (extraction chat + session embedding) — skipped when reusing users ---
        if not args.skip_ingest:
            for _sid, _sdt, turns in iter_sessions_capped(it, args.max_sessions_per_item):
                st = count_tokens(session_text(turns))
                if st == 0:
                    continue
                total_sessions += 1
                chat_prompt += extract_sys + st + 20
                chat_completion += min(int(0.3 * st), 512)
                chat_calls += 1
                embed_prompt += st          # proxy: facts embedded ≈ raw session text (upper bound)
                embed_calls += 1

        # --- recall: Tenax embeds the query; the recency baseline hits the DB only ---
        if getattr(args, "baseline", "none") != "recency":
            embed_prompt += count_tokens(it.get("question", ""))
            embed_calls += 1

        # --- reader + judge (skipped in retrieval-only) ---
        if not args.retrieval_only:
            chat_prompt += reader_sys + args.budget + count_tokens(it.get("question", "")) + 30
            chat_completion += 120
            chat_calls += 1
            chat_prompt += count_tokens(judge_prompt(it, "")) + 120
            chat_completion += 5
            chat_calls += 1

    chat_total = chat_prompt + chat_completion
    embed_total = embed_prompt
    n = len(items)
    summary = {
        "n_items": n,
        "sessions_ingested": total_sessions,
        "chat_prompt": chat_prompt, "chat_completion": chat_completion, "chat_total": chat_total,
        "embed_total": embed_total,
        "chat_calls": chat_calls, "embed_calls": embed_calls,
        "chat_fits_1M": chat_total < QUOTA_LIMIT,
        "embed_fits_1M": embed_total < QUOTA_LIMIT,
    }

    print("\n" + "=" * 60)
    print("LongMemEval — cost estimate (no API calls)")
    print("=" * 60)
    print(f"Items                      : {n}")
    print(f"Sessions to ingest         : {total_sessions}"
          + ("  (skipped: --skip-ingest)" if args.skip_ingest else ""))
    print("-" * 60)
    print(f"{'modality':<12}{'prompt':>12}{'completion':>12}{'total':>12}{'vs 1M':>8}")
    print("-" * 60)
    print(f"{'chat (LLM)':<12}{chat_prompt:>12,}{chat_completion:>12,}{chat_total:>12,}"
          f"{('OK' if summary['chat_fits_1M'] else 'OVER'):>8}")
    print(f"{'embed':<12}{embed_prompt:>12,}{'-':>12}{embed_total:>12,}"
          f"{('OK' if summary['embed_fits_1M'] else 'OVER'):>8}")
    print("-" * 60)
    print(f"Calls: {chat_calls:,} chat  +  {embed_calls:,} embed")
    print(f"Per item (avg): chat {chat_total // max(n,1):,} tok, embed {embed_total // max(n,1):,} tok")
    if not (summary["chat_fits_1M"] and summary["embed_fits_1M"]):
        print("\n⚠  Projected to EXCEED 1M on at least one modality — shrink --sample or "
              "--max-sessions-per-item, or split the run.")
    else:
        print("\n✓  Projected under 1M on both modalities (estimates are conservative/high).")
    print("=" * 60)
    print("Note: estimate only (over-estimates). No API calls, no DB writes.")
    return summary


# -------------------------------------------------------------------------------- main

def run(args) -> None:
    items = load_dataset(args.dataset)
    items = select_items(items, args)
    if not items:
        print("No items selected (check --offset/--limit/--sample/--categories).")
        return

    if args.estimate:
        estimate(items, args)
        return

    if args.dry_run:
        counts: dict[str, int] = defaultdict(int)
        undated = total_sess = max_sess = 0
        for it in items:
            counts[category_of(it)] += 1
            capped = iter_sessions_capped(it, args.max_sessions_per_item)
            total_sess += len(capped)
            max_sess = max(max_sess, len(capped))
            for _, sdt, _ in capped:
                undated += 1 if sdt is None else 0
        print(f"Dataset: {args.dataset}")
        print(f"Selected items: {len(items)}"
              + (f"  (stratified --sample {args.sample}, seed {args.seed})" if args.sample else ""))
        print("Per-category counts:")
        for cat in _CATEGORIES:
            if counts.get(cat):
                print(f"  {cat:<28}{counts[cat]:>4}")
        for cat in sorted(set(counts) - set(_CATEGORIES)):
            print(f"  {cat:<28}{counts[cat]:>4}  (unrecognized type)")
        cap_note = f" (cap {args.max_sessions_per_item})" if args.max_sessions_per_item else ""
        print(f"Sessions to ingest: {total_sess} total, max {max_sess}/item{cap_note}")
        if undated:
            print(f"WARNING: {undated} sessions had an unparseable date (will fall back to now()).")
        print("\nDry run only — no DB writes, no API calls.")
        return

    # engine/client need DB + QWEN_API_KEY: import late so --dry-run/--estimate stay free
    from app.memory.engine import MemoryEngine
    from app.qwen_client import QuotaExceeded, QwenClient

    client = QwenClient()
    engine = MemoryEngine(client)

    if args.rotate_models:
        if not args.shuffle:
            print("ERROR: --rotate-models requires --shuffle (the dataset is grouped by "
                  "category; rotating without shuffling biases per-category results).", file=sys.stderr)
            return
        pool = [m.strip() for m in args.rotation_models.split(",") if m.strip()]
        client.enable_rotation(pool)
        print(f"[rotate] extraction model rotation ON over {pool} "
              f"(reader/judge/embedding stay fixed; results labelled lower-validity).")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    stopped_early = False
    warned_quota = False
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as out_fh:
        for i, item in enumerate(items, 1):
            qid = item.get("question_id", f"item{i}")
            try:
                if args.skip_ingest:
                    n_sessions = None  # reuse the namespace ingested by a prior --keep-users run
                else:
                    n_sessions = ingest_item(
                        engine, item, granularity=args.granularity,
                        cheap=(args.cheap or args.cheap_extract),
                        max_sessions=args.max_sessions_per_item,
                    )
                record = eval_item(engine, client, item, args)
                record["n_sessions_ingested"] = n_sessions
            except QuotaExceeded as exc:
                # terminal: a model's 1M quota is spent. Checkpoint & stop cleanly —
                # completed items are already flushed to JSONL, so nothing is lost.
                print(f"\n[quota] Exhausted at item {i}/{len(items)} ({qid}): {exc}\n"
                      f"[quota] Stopping cleanly; {len(records)} item(s) completed and saved.",
                      file=sys.stderr)
                stopped_early = True
                break
            except KeyboardInterrupt:
                # manual Ctrl-C: checkpoint & stop cleanly instead of losing the summary
                # and the in-memory token/cost usage tallied so far.
                print(f"\n[interrupt] Stopped by user at item {i}/{len(items)} ({qid}); "
                      f"{len(records)} item(s) completed and saved.", file=sys.stderr)
                stopped_early = True
                break
            except Exception as exc:  # keep going; a single bad item shouldn't kill a long run
                record = {"question_id": qid, "category": category_of(item), "error": str(exc)}
                print(f"[{i}/{len(items)}] {qid}: ERROR {exc}", file=sys.stderr)
            records.append(record)
            out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_fh.flush()

            flag = ""
            if "error" not in record:
                if not args.retrieval_only:
                    flag = "✓" if record.get("correct") else "✗"
                he = record.get("retrieval_hit_evidence")
                hit = "-" if he is None else ("R+" if he else "R-")
                flag = f"{flag} {hit}".strip()
            print(f"[{i}/{len(items)}] {record.get('category',''):<26} {qid:<20} {flag}")

            u = client.usage()
            if not warned_quota and max(u["chat_total"], u["embed_total"]) >= QUOTA_WARN:
                warned_quota = True
                print(f"[quota] WARNING approaching 1M — chat {u['chat_total']:,}, "
                      f"embed {u['embed_total']:,}. Consider stopping / lowering --sample.",
                      file=sys.stderr)

        # keep namespaces if reusing them or if we stopped mid-run (so a resume can continue)
        if not args.keep_users and not stopped_early:
            for item in items:
                try:
                    engine.purge(f"bench:{item['question_id']}")
                except Exception:
                    pass

    good = [r for r in records if "error" not in r]
    summary = summarize(good, retrieval_only=args.retrieval_only)
    summary["elapsed_sec"] = round(time.time() - t0, 1)
    summary["errors"] = len(records) - len(good)
    summary["usage"] = client.usage()
    summary["config"] = {
        "dataset": args.dataset, "budget": args.budget, "candidate_k": args.candidate_k,
        "granularity": args.granularity, "cheap": args.cheap,
        "cheap_extract": args.cheap_extract, "baseline": args.baseline,
        "retrieval_only": args.retrieval_only, "judge_model": args.judge_model,
        "sample": args.sample, "seed": args.seed, "shuffle": args.shuffle,
        "max_sessions_per_item": args.max_sessions_per_item, "skip_ingest": args.skip_ingest,
        "rotate_models": args.rotate_models,
    }
    if stopped_early:
        summary["stopped_early"] = True
        summary["completed"] = len(records)
    print_summary(summary, retrieval_only=args.retrieval_only)
    u = summary["usage"]
    print(f"Tokens used  : chat {u['chat_total']:,} ({u['chat_calls']:,} calls)  |  "
          f"embed {u['embed_total']:,} ({u['embed_calls']:,} calls)")
    if summary["errors"]:
        print(f"({summary['errors']} item(s) errored — see stderr / JSONL)")
    if stopped_early:
        print(f"⚠ Stopped early on quota after {len(records)} item(s); results are partial.")

    summary_path = out_path.with_suffix(".summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"\nPer-item records : {out_path}")
    print(f"Summary          : {summary_path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LongMemEval harness for Tenax")
    p.add_argument("--dataset", required=True, help="path to longmemeval_s.json (or _m / _oracle)")
    p.add_argument("--out", default="benchmark/results/longmemeval.jsonl", help="per-item JSONL output")
    p.add_argument("--budget", type=int, default=1200, help="recall token budget (context size)")
    p.add_argument("--candidate-k", type=int, default=50, help="candidates pulled per index before scoring")
    p.add_argument("--granularity", choices=("session", "turn"), default="session",
                   help="ingest one remember() per session (cheaper) or per turn")
    p.add_argument("--cheap", action="store_true", help="use the cheap Qwen model for extraction + reader")
    p.add_argument("--cheap-extract", action="store_true",
                   help="use the cheap Qwen model for extraction (+belief-revision) only, keeping the "
                        "main model for the reader. Extraction is mechanical; the reader does the "
                        "reasoning — this cuts ingest cost/time without touching answer quality.")
    p.add_argument("--retrieval-only", action="store_true",
                   help="skip reader+judge; measure only retrieval hit-rate + tokens (cheap)")
    p.add_argument("--judge-model", default=None, help="override judge model (default: chat model)")
    p.add_argument("--limit", type=int, default=0, help="only run the first N selected items (0 = all)")
    p.add_argument("--offset", type=int, default=0, help="skip the first N items")
    p.add_argument("--categories", default=None, help="comma-separated category filter")
    p.add_argument("--ids", default=None,
                   help="comma-separated question_ids to run exactly (before/after re-runs); "
                        "supersedes --sample/--limit/--offset")
    p.add_argument("--keep-users", action="store_true", help="do not purge bench users after the run")
    p.add_argument("--dry-run", action="store_true", help="parse + report only; no DB, no API")
    # --- Langkah 2: free-tier sampling / cost control ---
    p.add_argument("--sample", type=int, default=0,
                   help="stratified sample of N items across the 7 categories (supersedes --limit/--offset)")
    p.add_argument("--shuffle", action="store_true",
                   help="shuffle item order (seeded); decorrelates order from category (needed with --rotate-models)")
    p.add_argument("--seed", type=int, default=13, help="seed for --sample / --shuffle (deterministic)")
    p.add_argument("--max-sessions-per-item", type=int, default=0,
                   help="cap sessions ingested/question (keeps all evidence sessions); 0 = no cap")
    p.add_argument("--estimate", action="store_true",
                   help="project chat & embed token cost vs 1M and exit; no DB, no API")
    p.add_argument("--skip-ingest", action="store_true",
                   help="reuse bench namespaces from a prior --keep-users run (eval only, no extraction)")
    p.add_argument("--baseline", choices=("none", "recency"), default="none",
                   help="'recency' = naive most-recent recall strawman instead of Tenax hybrid recall")
    p.add_argument("--rotate-models", action="store_true",
                   help="opt-in: rotate the EXTRACTION model on quota-exceeded (requires --shuffle; lower validity)")
    p.add_argument("--rotation-models", default="qwen-turbo,qwen-plus",
                   help="comma-separated extraction-model pool for --rotate-models")
    return p


def main() -> None:
    # Windows consoles/pipes default to cp1252, which crashes on the ✓/✗/⚠ status glyphs
    # this harness prints. Force UTF-8 so a long run never dies at a progress line.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
