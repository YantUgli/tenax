"""V0 — deterministic mechanism test for Tier 1 (temporal validity / event_time).

Validates the *mechanism* of Mechanism A without a database, a reader, or any Qwen
call, so it can run in CI or before spending reader quota:

1. event-date parsing     — the extractor's ISO string -> UTC datetime (tolerant).
2. recall rendering/order  — a memory carrying an ``event_time`` renders its dated
   prefix from the event date (not created_at) and the context reads in event-time
   chronological order.
3. created_at fallback     — a memory with no ``event_time`` still renders/sorts on
   created_at, so facts without a datable anchor behave exactly as before.

This does NOT measure answer accuracy — that is V1 (benchmark/longmemeval.py --ids).
Run:  <venv-python> -m benchmark.temporal_check
Exit code 0 = all checks pass, 1 = a check failed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.memory.extract import _parse_event_date
from app.memory.models import MemStatus
from app.memory.retrieve import _anchor, _chrono_key, _render_line


def _mem(*, content, created_at, event_time=None, status=MemStatus.active, superseded_by=None):
    """A duck-typed stand-in for a Memory row (render helpers only touch these fields)."""
    return SimpleNamespace(
        content=content,
        created_at=created_at,
        event_time=event_time,
        status=status,
        superseded_by=superseded_by,
    )


def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


_PASS = "[ok]"
_FAIL = "[XX]"
_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {_PASS if cond else _FAIL} {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        _failures.append(f"{name} {detail}".strip())


def test_parse() -> None:
    print("1. event-date parsing")
    check("ISO date", _parse_event_date("2023-05-14") == _utc(2023, 5, 14))
    check("month-only resolved upstream", _parse_event_date("2023-03-01") == _utc(2023, 3, 1))
    check("full ISO timestamp with Z",
          _parse_event_date("2023-05-14T10:00:00Z") == datetime(2023, 5, 14, 10, tzinfo=timezone.utc))
    check("single-digit parts", _parse_event_date("2023-5-3") == _utc(2023, 5, 3))
    for bad in (None, "", "null", "back in March", "garbage", 123):
        check(f"non-date -> None: {bad!r}", _parse_event_date(bad) is None)


def test_anchor_and_render() -> None:
    print("2. anchor + dated render")
    # event_time present -> prefix and anchor use the EVENT date, not created_at.
    m = _mem(content="Started new job", created_at=_utc(2023, 6, 15), event_time=_utc(2023, 6, 12))
    check("anchor prefers event_time", _anchor(m) == _utc(2023, 6, 12))
    line = _render_line(m, {})
    check("render uses event date", line == "- [2023-06-12] Started new job", detail=line)

    # no event_time -> falls back to created_at (unchanged legacy behaviour).
    m2 = _mem(content="Likes tea", created_at=_utc(2023, 6, 15), event_time=None)
    check("anchor falls back to created_at", _anchor(m2) == _utc(2023, 6, 15))
    check("render falls back to created_at",
          _render_line(m2, {}) == "- [2023-06-15] Likes tea", detail=_render_line(m2, {}))

    # superseded fact renders PAST tag with the successor's takeover date.
    past = _mem(content="Lived in Paris", created_at=_utc(2020, 1, 1), event_time=_utc(2020, 1, 1),
                status=MemStatus.archived, superseded_by=99)
    line_p = _render_line(past, {99: _utc(2022, 3, 1)})
    check("PAST tag uses successor date",
          line_p == "- [2020-01-01] PAST (superseded on 2022-03-01): Lived in Paris", detail=line_p)


def test_chrono_order() -> None:
    print("3. chronological ordering by event_time")
    # Recorded out of order, but event dates should drive the sort.
    a = _mem(content="Muir Woods hike", created_at=_utc(2023, 5, 20), event_time=_utc(2023, 3, 10))
    b = _mem(content="Big Sur road trip", created_at=_utc(2023, 5, 20), event_time=_utc(2023, 4, 15))
    c = _mem(content="Yosemite camping", created_at=_utc(2023, 5, 20), event_time=_utc(2023, 5, 2))
    ordered = sorted([c, a, b], key=_chrono_key)
    got = [m.content for m in ordered]
    check("events sort by event date, not record date",
          got == ["Muir Woods hike", "Big Sur road trip", "Yosemite camping"], detail=str(got))

    # A mix: event-dated facts interleave correctly with a created_at-only fact.
    d = _mem(content="undated pref", created_at=_utc(2023, 4, 1), event_time=None)
    got2 = [m.content for m in sorted([c, d, a], key=_chrono_key)]
    check("event-dated + fallback interleave by anchor",
          got2 == ["Muir Woods hike", "undated pref", "Yosemite camping"], detail=str(got2))


def main() -> int:
    print("=" * 60)
    print("V0 temporal-validity mechanism check (no DB, no Qwen)")
    print("=" * 60)
    test_parse()
    test_anchor_and_render()
    test_chrono_order()
    print("-" * 60)
    if _failures:
        print(f"FAIL — {len(_failures)} check(s) failed:")
        for f in _failures:
            print(f"   - {f}")
        return 1
    print("PASS - event_time parsing, dated render, and chronological order all correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
