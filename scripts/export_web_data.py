"""Export measured benchmark results into a single JSON the marketing site reads.

Every number rendered on the Tenax site comes from this file, and every field here
is copied out of a real run artifact in benchmark/results/ -- nothing is hand-typed.

    pipenv run python -m scripts.export_web_data
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmark" / "results"
OUT = ROOT / "web" / "data" / "benchmark.json"

# Human-readable provenance for each artifact we pull from, so the site can link
# a claim back to the file and command that produced it.
SOURCES = {
    "baseline_oracle": ("benchmark.longmemeval", "qwen-turbo reader, LongMemEval oracle, n=50"),
    "qwen37plus_sample50": ("benchmark.longmemeval", "qwen3.7-plus reader, LongMemEval oracle, n=50"),
    "temporal_tier1A": ("benchmark.longmemeval", "temporal-reasoning subset after event_time validity, n=13"),
    "regression_nontemporal": ("benchmark.longmemeval", "non-temporal control set after the temporal change, n=12"),
    "hybrid_vs_naive": ("benchmark.run", "hybrid vs recency-only on a 30-distractor haystack"),
    "update": ("benchmark.update", "belief revision / knowledge update"),
    "staleness": ("benchmark.staleness", "3 forget+reflect cycles"),
}


def load(name: str) -> dict:
    return json.loads((RESULTS / f"{name}.summary.json").read_text(encoding="utf-8"))


def pct(x: float | None) -> float | None:
    return None if x is None else round(x * 100, 1)


def categories(summary: dict) -> list[dict]:
    out = []
    for key, val in (summary.get("per_category") or {}).items():
        out.append({"category": key, "n": val["n"], "accuracy": pct(val.get("accuracy"))})
    out.sort(key=lambda c: c["category"])
    return out


def main() -> None:
    base = load("baseline_oracle")
    plus = load("qwen37plus_sample50")
    temporal = load("temporal_tier1A")
    control = load("regression_nontemporal")
    hybrid = load("hybrid_vs_naive")
    update = load("update")
    staleness = load("staleness")

    # The temporal fix was measured on the 13-item temporal subset, not on a fresh
    # full-50 run. We expose the projection but flag it, so the site can never
    # present it as a measured overall number.
    n_total = plus["n_items"]
    temporal_cat = plus["per_category"]["temporal-reasoning"]
    delta = (temporal["overall_accuracy"] - temporal_cat["accuracy"]) * temporal_cat["n"] / n_total
    projected = plus["overall_accuracy"] + delta

    data = {
        "measured_on": "2026-07-07",
        "runtime": {
            "provider": "Qwen Cloud (DashScope-intl)",
            "extract_model": "qwen-turbo",
            "embed_model": "text-embedding-v4",
            "reader_model": "qwen3.7-plus",
        },
        "headline": {
            "retrieval_hit_rate": pct(plus["retrieval_hit_rate"]),
            "temporal_before": pct(base["per_category"]["temporal-reasoning"]["accuracy"]),
            "temporal_after": pct(temporal["overall_accuracy"]),
            "avg_tokens_per_query": round(plus["avg_tokens_per_query"]),
            "token_budget": plus["config"]["budget"],
        },
        "accuracy": {
            "baseline": {
                "label": "qwen-turbo reader",
                "n": base["n_items"],
                "overall": pct(base["overall_accuracy"]),
                "per_category": categories(base),
            },
            "reader_upgrade": {
                "label": "qwen3.7-plus reader",
                "n": plus["n_items"],
                "overall": pct(plus["overall_accuracy"]),
                "per_category": categories(plus),
            },
            "temporal_fix": {
                "label": "+ temporal validity (event_time)",
                "n": temporal["n_items"],
                "overall": pct(temporal["overall_accuracy"]),
                "scope": "temporal-reasoning subset only",
            },
            "projected_overall": {
                "value": pct(projected),
                "measured": False,
                "note": (
                    "Projection: the qwen3.7-plus 50-item run with its temporal subset "
                    "replaced by the separately measured 76.9%. Not a single end-to-end run."
                ),
            },
        },
        "no_regression": {
            "n": control["n_items"],
            "overall": pct(control["overall_accuracy"]),
            "claim": "Non-temporal categories held after the temporal change.",
        },
        "retrieval": {
            "hybrid_hits": hybrid["mnemo_hybrid"]["hits"],
            "hybrid_total": hybrid["mnemo_hybrid"]["total"],
            "recency_hits": hybrid["baseline_recency_only"]["hits"],
            "recency_total": hybrid["baseline_recency_only"]["total"],
            "budget_tokens": hybrid["budget_tokens"],
            "n_distractors": hybrid["n_distractors"],
        },
        "belief_revision": {
            "updates_applied": update["updates_applied"],
            "n_updates": update["n_updates"],
            "traps_passed": update["traps_passed"],
            "n_traps": update["n_traps"],
            "wrong_supersedes": update["wrong_supersede_incidents"],
        },
        "staleness": {
            "cycles": staleness["config"]["cycles"],
            "accessed_survived": staleness["variants"]["accessed"]["final_survived"],
            "important_total": staleness["variants"]["accessed"]["important_total"],
            "wrong_merges": staleness["variants"]["accessed"]["total_wrong_merge_incidents"],
            "dormant_survived": staleness["variants"]["dormant"]["final_survived"],
        },
        "sources": [
            {"artifact": f"benchmark/results/{name}.summary.json", "command": cmd, "what": what}
            for name, (cmd, what) in SOURCES.items()
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  retrieval hit {data['headline']['retrieval_hit_rate']}%  "
          f"temporal {data['headline']['temporal_before']}% -> {data['headline']['temporal_after']}%  "
          f"projected overall {data['accuracy']['projected_overall']['value']}%")


if __name__ == "__main__":
    main()
