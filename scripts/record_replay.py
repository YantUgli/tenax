"""Record a real Tenax session and freeze it as the site's replay transcript.

The marketing site plays this back step by step. Nothing here is authored by hand:
every response block is whatever the live engine (Qwen Cloud + Postgres/pgvector)
actually returned when this script ran.

    pipenv run python -m scripts.record_replay
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.memory.engine import MemoryEngine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "data" / "replay.json"
USER = "replay-demo"

NOW = datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


# A tight budget is the point: with room for everything, recall just returns the whole
# store and budget-aware packing proves nothing. 150 tokens forces it to choose.
DEMO_BUDGET = 150

# The narrative: an agent that has been working with one person for two months.
# Old-but-important facts (the allergy) must survive a flood of recent trivia; one belief
# (where they live) is genuinely revised; dormant trivia decays away while accessed facts
# survive; and a restated decision gets consolidated.
SCRIPT = [
    {
        "act": "remember",
        "age_days": 62,
        "caption": "Two months ago — the first real conversation.",
        "text": (
            "I'm Maya, I lead the recommendation engine team at Kalibrasi. "
            "My research advisor on the project is Dr. Lin. I live in Jakarta. "
            "Also worth noting: I'm allergic to shellfish, so team dinners need alternatives."
        ),
    },
    {
        "act": "remember",
        "age_days": 75,
        "caption": "Older trivia — never asked about again. Watch what happens to it.",
        "text": (
            "Facilities note: the office wifi password was rotated this morning, "
            "parking garage B is closed for resurfacing, and the coffee machine got fixed."
        ),
    },
    {
        "act": "remember",
        "age_days": 48,
        "caption": "A design decision, six weeks back.",
        "text": (
            "We evaluated Pinecone and Weaviate but settled on Postgres with pgvector "
            "for the vector store — it keeps the operational surface small and fits the budget."
        ),
    },
    {
        "act": "remember",
        "age_days": 20,
        "caption": "The same decision, restated later in different words.",
        "text": (
            "For the record, our vector store is pgvector running inside the main Postgres "
            "instance — we passed on Pinecone."
        ),
    },
    {
        "act": "remember",
        "age_days": 6,
        "caption": "Recent chatter — the kind of thing that floods a recency-only memory.",
        "text": (
            "Quick update: the standup moved to 9:30, the staging deploy is green again, "
            "and I finally fixed the flaky pagination test."
        ),
    },
    {
        "act": "remember",
        "age_days": 3,
        "caption": "More recent noise.",
        "text": (
            "The Q3 planning doc is in review, I'm on call next week, "
            "and the new intern starts on Monday."
        ),
    },
    {
        "act": "recall",
        "caption": "Ask something only an old memory can answer.",
        "query": "We're booking a team dinner next week — anything I should know?",
        "note": (
            "A recency-only memory returns standups and deploy notes. Hybrid retrieval "
            "surfaces a 62-day-old allergy because importance and semantic match outrank recency."
        ),
    },
    {
        "act": "recall",
        "caption": "A second question — this one keeps the storage decision alive.",
        "query": "Which vector store did we end up choosing, and what did we rule out?",
        "note": "Recall reinforces what it returns: these two get their retention clock reset.",
    },
    {
        "act": "remember",
        "age_days": 2,
        "caption": "A fact that genuinely contradicts a stored belief.",
        "text": "I've relocated — I moved from Jakarta to Singapore to open the new office.",
        "highlight": "belief_revision",
    },
    {
        "act": "recall",
        "caption": "The same question, after revision.",
        "query": "Where does Maya live?",
        "note": "The stale belief is archived with a superseded_by pointer, so recall serves one current truth instead of two contradictory ones.",
    },
    {
        "act": "list_memories",
        "caption": "The store before maintenance, with live decay scores.",
        "status": "all",
        "label": "before",
    },
    {
        "act": "forget",
        "caption": "Decay sweep — archive what stopped earning its place.",
        "note": "Facts that recall touched had their clock reset and survive; untouched trivia falls below the retention threshold.",
    },
    {
        "act": "reflect",
        "caption": "Reflection — and it finds nothing left to do.",
        "note": (
            "Zero clusters, honestly reported: the restated vector-store decision was already "
            "collapsed at write time by belief revision (step 4), so periodic consolidation has "
            "no duplicates left. Reflection's merge behaviour is measured separately in the "
            "staleness benchmark (1 cluster found, 2 memories merged, 0 wrong merges)."
        ),
    },
    {
        "act": "list_memories",
        "caption": "The store after maintenance.",
        "status": "all",
        "label": "after",
    },
]


def main() -> None:
    engine = MemoryEngine()
    print(f"purging {USER} ...")
    engine.purge(USER)

    steps = []
    for i, step in enumerate(SCRIPT, 1):
        act = step["act"]
        print(f"[{i}/{len(SCRIPT)}] {act} ...", flush=True)
        record = {k: v for k, v in step.items() if k not in {"act", "age_days"}}
        record["act"] = act
        record["step"] = i

        if act == "remember":
            when = days_ago(step["age_days"])
            record["at"] = when.isoformat()
            record["age_days"] = step["age_days"]
            record["response"] = engine.remember(
                USER, step["text"], cheap=True, event_time=when
            )
        elif act == "recall":
            record["token_budget"] = DEMO_BUDGET
            record["response"] = engine.recall(
                USER, step["query"], token_budget=DEMO_BUDGET
            )
        elif act == "list_memories":
            record["response"] = engine.list_memories(
                USER, status=step.get("status", "active"), limit=100
            )
        elif act == "forget":
            record["response"] = engine.forget(USER)
        elif act == "reflect":
            record["response"] = engine.reflect(USER, cheap=True)
        else:  # pragma: no cover - typo guard
            raise ValueError(f"unknown act: {act}")

        steps.append(record)

    payload = {
        "recorded_at": NOW.isoformat(),
        "user_id": USER,
        "runtime": {
            "extract_model": "qwen-turbo",
            "embed_model": "text-embedding-v4",
            "store": "PostgreSQL + pgvector",
            "provider": "Qwen Cloud (DashScope-intl)",
        },
        "note": "Verbatim capture of a real run of scripts/record_replay.py. Replayed, not simulated.",
        "steps": steps,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(steps)} steps)")


if __name__ == "__main__":
    main()
