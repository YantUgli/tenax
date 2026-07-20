"""ORM model for a single memory row.

A memory is a self-contained statement with provenance and the metadata needed for
the three core Track-1 behaviours: efficient retrieval (embedding + FTS), forgetting
(created_at / last_accessed / access_count / importance), and consolidation (mem_type,
status, superseded_by).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

_EMBED_DIM = get_settings().embed_dim


class Base(DeclarativeBase):
    pass


class MemType(str, enum.Enum):
    episodic = "episodic"   # raw events / interactions
    semantic = "semantic"   # distilled, canonical facts
    procedural = "procedural"  # learned preferences / how-to (stretch)


class MemStatus(str, enum.Enum):
    active = "active"
    archived = "archived"  # soft-forgotten or superseded by consolidation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    content: Mapped[str] = mapped_column(Text)
    mem_type: Mapped[MemType] = mapped_column(Enum(MemType, name="mem_type"), default=MemType.episodic)
    importance: Mapped[float] = mapped_column(Float, default=5.0)  # 1..10 as scored at write time

    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBED_DIM))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_accessed: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    # When the fact is temporally anchored — the date the event happened or the state
    # began — as opposed to created_at (when Tenax recorded it). Set from the absolute
    # date the extractor resolves out of the text ("last Tuesday" -> 2023-05-09). Used
    # ONLY for temporal rendering/ordering at recall; decay and recency still key off
    # created_at/last_accessed, so the forgetting behaviour is unchanged. Null when the
    # text carries no datable anchor (recall then falls back to created_at).
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[MemStatus] = mapped_column(
        Enum(MemStatus, name="mem_status"), default=MemStatus.active, index=True
    )
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def as_dict(self, *, include_embedding: bool = False) -> dict:
        d = {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "mem_type": self.mem_type.value if isinstance(self.mem_type, MemType) else self.mem_type,
            "importance": self.importance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "status": self.status.value if isinstance(self.status, MemStatus) else self.status,
            "source": self.source,
            "superseded_by": self.superseded_by,
        }
        if include_embedding:
            d["embedding"] = list(self.embedding) if self.embedding is not None else None
        return d
