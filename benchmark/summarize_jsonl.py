"""Rebuild a LongMemEval summary from one or more per-item JSONL result files.

Every item is flushed to the ``--out`` JSONL immediately after it completes, so a run
that stops early (Ctrl-C, quota exhaustion, a hard crash, or you killing it manually to
control spend) never loses completed items — only the final summary.json is missing.
This script reconstructs that summary from whatever JSONL is on disk, using the exact
same ``summarize()``/``print_summary()`` the harness itself uses, so the numbers are
directly comparable to a full run's output.

Caveat: real API token/cost usage (``client.usage()``) lives only in the harness
process's memory and is not stored per JSONL line, so it cannot be recovered here if the
process died before writing its own summary.json — cross-check actual spend against the
DashScope usage dashboard instead.

Usage:
    pipenv run python -m benchmark.summarize_jsonl benchmark/results/run.jsonl
    pipenv run python -m benchmark.summarize_jsonl part1.jsonl part2.jsonl --out combined.summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmark.longmemeval import print_summary, summarize


def load_records(paths: list[Path]) -> list[dict]:
    records: list[dict] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def main() -> None:
    p = argparse.ArgumentParser(description="Rebuild a summary from partial/complete JSONL results")
    p.add_argument("jsonl", nargs="+", help="one or more --out JSONL files to combine")
    p.add_argument("--out", help="save the reconstructed summary here (default: <first file>.reconstructed_summary.json)")
    args = p.parse_args()

    paths = [Path(f) for f in args.jsonl]
    records = load_records(paths)
    if not records:
        print("No records found in the given file(s).", file=sys.stderr)
        sys.exit(1)

    good = [r for r in records if "error" not in r]
    errors = [r for r in records if "error" in r]
    # a retrieval-only run never writes "correct" onto any record
    retrieval_only = not any("correct" in r for r in good)

    summary = summarize(good, retrieval_only=retrieval_only)
    summary["source_files"] = [str(p) for p in paths]
    summary["errors"] = len(errors)
    summary["note"] = "reconstructed from JSONL; real token/cost usage not recoverable here"

    print_summary(summary, retrieval_only=retrieval_only)
    print(f"Items total (incl. errors) : {len(records)}")
    if errors:
        print(f"Errored item_ids           : {[r.get('question_id') for r in errors]}")

    out_path = Path(args.out) if args.out else paths[0].with_suffix(".reconstructed_summary.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
