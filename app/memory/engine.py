"""MemoryEngine — the public façade the MCP server, REST API, demo, and benchmark all use.

It owns a single Qwen client and runs each operation inside a transactional session.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db import session_scope
from app.memory import consolidate as _consolidate
from app.memory import extract as _extract
from app.memory import forget as _forget
from app.memory import retrieve as _retrieve
from app.memory.models import Memory, MemStatus, MemType
from app.qwen_client import QwenClient


class MemoryEngine:
    def __init__(self, client: QwenClient | None = None) -> None:
        self._client = client or QwenClient()

    # -------------------------------------------------------------- write
    def remember(self, user_id: str, text: str, *, source: str | None = None, cheap: bool = False) -> dict:
        extracted = _extract.extract_memories(self._client, text, cheap=cheap)
        if not extracted:
            return {"created": [], "note": "nothing worth remembering"}

        embeddings = self._client.embed([e["content"] for e in extracted])
        created = []
        with session_scope() as session:
            for e, emb in zip(extracted, embeddings):
                mem = Memory(
                    user_id=user_id,
                    content=e["content"],
                    mem_type=MemType(e["mem_type"]),
                    importance=e["importance"],
                    embedding=emb,
                    source=source,
                )
                session.add(mem)
                session.flush()
                created.append(mem.as_dict())
        return {"created": created}

    # --------------------------------------------------------------- read
    def recall(self, user_id: str, query: str, *, token_budget: int | None = None, candidate_k: int = 30) -> dict:
        with session_scope() as session:
            return _retrieve.retrieve(
                session, self._client, user_id, query,
                token_budget=token_budget, candidate_k=candidate_k,
            )

    # ------------------------------------------------------------- forget
    def forget(self, user_id: str, *, threshold: float | None = None) -> dict:
        with session_scope() as session:
            return _forget.sweep(session, user_id, threshold=threshold)

    # ------------------------------------------------------------ reflect
    def reflect(self, user_id: str, *, threshold: float | None = None) -> dict:
        with session_scope() as session:
            return _consolidate.consolidate(session, self._client, user_id, threshold=threshold)

    # -------------------------------------------------------------- utils
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
