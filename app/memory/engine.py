"""MemoryEngine — the public façade the MCP server, REST API, demo, and benchmark all use.

It owns a single Qwen client and runs each operation inside a transactional session.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select

from app.db import session_scope
from app.memory import consolidate as _consolidate
from app.memory import extract as _extract
from app.memory import forget as _forget
from app.memory import retrieve as _retrieve
from app.memory import revise as _revise
from app.memory.models import Memory, MemStatus, MemType
from app.qwen_client import QwenClient


class MemoryEngine:
    def __init__(self, client: QwenClient | None = None) -> None:
        self._client = client or QwenClient()

    # -------------------------------------------------------------- write
    def remember(
        self,
        user_id: str,
        text: str,
        *,
        source: str | None = None,
        cheap: bool = False,
        event_time: datetime | None = None,
    ) -> dict:
        """Extract and persist memories from ``text``.

        ``event_time`` back-dates the created rows: when a memory refers to something that
        happened at a known past time (e.g. replaying a multi-session benchmark history),
        pass the session timestamp so ``created_at``/``last_accessed`` reflect *when the
        event occurred* rather than now(). This is what makes temporal reasoning and
        recency measurable — without it every replayed memory looks equally recent.
        """
        extracted = _extract.extract_memories(
            self._client, text, cheap=cheap, event_time=event_time
        )
        if not extracted:
            return {"created": [], "note": "nothing worth remembering"}

        embeddings = self._client.embed([e["content"] for e in extracted])
        created = []
        with session_scope() as session:
            new_mems: list[Memory] = []
            for e, emb in zip(extracted, embeddings):
                mem = Memory(
                    user_id=user_id,
                    content=e["content"],
                    mem_type=MemType(e["mem_type"]),
                    importance=e["importance"],
                    embedding=emb,
                    source=source,
                )
                if event_time is not None:
                    mem.created_at = event_time
                    mem.last_accessed = event_time
                # Temporal anchor for recall ordering: the date the extractor resolved out
                # of the fact itself ("last Tuesday" -> 2023-05-09) when present, else the
                # session/event time. Kept separate from created_at so decay is unaffected.
                mem.event_time = e.get("event_time") or event_time
                session.add(mem)
                session.flush()
                new_mems.append(mem)
                created.append(mem.as_dict())
            # Belief revision: archive stored facts the new ones genuinely update or
            # contradict (superseded_by -> new id). No similar candidates = no LLM call.
            revision = _revise.revise(session, self._client, user_id, new_mems, cheap=cheap)
        return {"created": created, "superseded": revision["superseded"]}

    # --------------------------------------------------------------- read
    def recall(self, user_id: str, query: str, *, token_budget: int | None = None, candidate_k: int = 30) -> dict:
        with session_scope() as session:
            return _retrieve.retrieve(
                session, self._client, user_id, query,
                token_budget=token_budget, candidate_k=candidate_k,
            )

    # ------------------------------------------------------------- forget
    def forget(
        self, user_id: str, *, threshold: float | None = None, now: datetime | None = None
    ) -> dict:
        """Run the decay sweep. ``now`` lets a benchmark drive a simulated clock so
        multiple forget cycles can be measured without waiting real wall-clock time."""
        with session_scope() as session:
            return _forget.sweep(session, user_id, threshold=threshold, now=now)

    # ------------------------------------------------------------ reflect
    def reflect(
        self, user_id: str, *, threshold: float | None = None, cheap: bool = False
    ) -> dict:
        """Consolidate near-duplicate memories. ``cheap`` routes the distillation LLM to
        the cheap model (qwen-turbo); the default chat model is used otherwise."""
        with session_scope() as session:
            return _consolidate.consolidate(
                session, self._client, user_id, threshold=threshold, cheap=cheap
            )

    # -------------------------------------------------------------- utils
    def purge(self, user_id: str) -> dict:
        """Hard-delete every memory for ``user_id``.

        Benchmark isolation primitive: each question owns its own history under a unique
        ``user_id`` (e.g. ``bench:{item_id}``), and ``purge`` resets that namespace cleanly
        so no facts leak between questions. Unlike ``forget``, this deletes rather than
        archives — it is for test setup/teardown, not for the self-managing memory loop.
        """
        with session_scope() as session:
            deleted = session.execute(
                delete(Memory).where(Memory.user_id == user_id)
            ).rowcount
        return {"user_id": user_id, "deleted": int(deleted or 0)}

    def list_memories(self, user_id: str, *, status: str = "active", limit: int = 100) -> list[dict]:
        with session_scope() as session:
            stmt = select(Memory).where(Memory.user_id == user_id)
            if status != "all":
                stmt = stmt.where(Memory.status == MemStatus(status))
            stmt = stmt.order_by(Memory.created_at.desc()).limit(limit)
            rows = session.scalars(stmt).all()
            enriched = []
            for m in rows:
                d = m.as_dict()
                d["decay_score"] = round(_forget.decay_score(m), 4)
                enriched.append(d)
            return enriched

    def stats(self, user_id: str) -> dict:
        with session_scope() as session:
            by_status = dict(
                session.execute(
                    select(Memory.status, func.count())
                    .where(Memory.user_id == user_id)
                    .group_by(Memory.status)
                ).all()
            )
            by_type = dict(
                session.execute(
                    select(Memory.mem_type, func.count())
                    .where(Memory.user_id == user_id, Memory.status == MemStatus.active)
                    .group_by(Memory.mem_type)
                ).all()
            )
            total = session.scalar(select(func.count()).select_from(Memory).where(Memory.user_id == user_id))
            return {
                "user_id": user_id,
                "total": total or 0,
                "by_status": {k.value: v for k, v in by_status.items()},
                "active_by_type": {k.value: v for k, v in by_type.items()},
            }
