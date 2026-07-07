"""Benchmark instrumentation: separate a *memory* failure from a *reader* failure.

`retrieval_hit` answers, per question, whether the gold fact actually surfaced in the
retrieved ``context``. This is the pivot the decision gate (Langkah 5, criterion 4) turns
on: if the gold is present but the model still answers wrong, the fault is the *reader*;
if the gold is absent, the fault is *retrieval* — i.e. the core memory. Retrieval hit-rate
is therefore the sharpest signal of whether the memory core is ready to be extended.
"""
from __future__ import annotations

from collections.abc import Iterable


def _norm(s: str) -> str:
    """Lowercase + collapse whitespace so matching ignores casing and formatting noise."""
    return " ".join((s or "").lower().split())


def retrieval_hit(context: str, gold: str | Iterable[str], *, mode: str = "any") -> bool:
    """Return True if the gold fact appears in the retrieved ``context``.

    ``gold`` may be a single string or several acceptable strings/keywords (LongMemEval
    items often carry multiple valid answer spans). Matching is case-insensitive,
    whitespace-normalized substring containment.

    ``mode="any"`` (default) counts a hit if *any* gold string is present; ``mode="all"``
    requires *every* one — useful for multi-hop answers where all pieces must be recalled.
    """
    ctx = _norm(context)
    if not ctx:
        return False
    if gold is None:
        return False
    # LongMemEval answers may be a string, a number (e.g. temporal "how many days"), or a
    # list of acceptable spans — coerce everything to strings before matching.
    if isinstance(gold, str):
        golds = [gold]
    elif isinstance(gold, Iterable):
        golds = [str(g) for g in gold]
    else:
        golds = [str(gold)]
    tests = [(_norm(g) in ctx) for g in golds if _norm(g)]
    if not tests:
        return False
    return all(tests) if mode == "all" else any(tests)
