"""Belief revision: write-time knowledge-update / contradiction handling.

Contradicting facts ("works at Google" vs "moved to Microsoft") are usually NOT similar
enough to land in the same reflect() cluster, so without this step they sit side by side
and poison recall — the reader sees both and guesses. Belief revision runs at remember()
time: each newly written fact is checked against similar *active* facts of the same user,
and when the new fact genuinely updates or contradicts an old one, the old row is archived
with ``superseded_by`` pointing at its replacement. recall() only surfaces active rows, so
stale beliefs drop out of the context immediately.

Cost profile (free-tier discipline): candidate detection is pure pgvector (~0 quota); the
LLM confirmation is ONE cheap chat_json call per remember() batch, and only when at least
one candidate pair exists — a remember() into a namespace with no similar facts makes no
chat call at all.
"""
from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.memory.models import Memory, MemStatus
from app.qwen_client import QwenClient

# Bound the confirmation prompt on large ingests.
_MAX_CANDIDATES_PER_MEMORY = 3
_MAX_PAIRS_PER_BATCH = 20

_SYSTEM = (
    "You are the belief-revision module of a long-term memory system. You get numbered "
    "pairs, each with a NEW fact just learned and an OLD fact already stored. Decide for "
    "each pair whether the NEW fact SUPERSEDES the OLD one: they must describe the SAME "
    "attribute of the SAME entity, with the new value replacing the old (an update or a "
    "direct contradiction).\n"
    "Rules:\n"
    "- Supersede ONLY on a genuine update/contradiction of the same attribute of the same "
    "entity (e.g. 'works at Google' -> 'now works at Microsoft').\n"
    "- Facts about DIFFERENT entities are NEVER superseded (daughter Mia vs son Leo).\n"
    "- COMPLEMENTARY facts (different attributes of one entity: job vs hobby, color vs "
    "size) are NOT superseded.\n"
    "- Additions are NOT supersessions: 'likes tea' does not supersede 'likes coffee' "
    "unless the new fact says the old preference no longer holds.\n"
    "- When unsure, do NOT supersede.\n"
    'Respond ONLY as JSON: {"supersede": [<pair numbers where NEW supersedes OLD>]}'
)


def revise(
    session,
    client: QwenClient,
    user_id: str,
    new_memories: list[Memory],
    *,
    cheap: bool = False,
) -> dict:
    """Check ``new_memories`` (already flushed, ids assigned) against stored active facts
    and archive the ones they supersede. Returns a summary dict."""
    s = get_settings()
    if not s.revise_enabled or not new_memories:
        return {"pairs_checked": 0, "superseded": [], "llm_calls": 0}

    new_ids = [m.id for m in new_memories]
    dist_cap = 1.0 - s.revise_similarity

    # --- candidate pairs via pgvector (no LLM, no extra embeddings) ---
    scored_pairs: list[tuple[float, Memory, Memory]] = []  # (distance, new, old)
    for new in new_memories:
        emb = list(new.embedding)
        dist = Memory.embedding.cosine_distance(emb)
        rows = session.execute(
            select(Memory, dist.label("dist"))
            .where(
                Memory.user_id == user_id,
                Memory.status == MemStatus.active,
                Memory.id.not_in(new_ids),
                dist <= dist_cap,
            )
            .order_by(dist)
            .limit(_MAX_CANDIDATES_PER_MEMORY)
        ).all()
        scored_pairs.extend((float(r.dist), new, r.Memory) for r in rows)

    # On dense same-topic corpora many benign pairs enter the band; keep the globally
    # most-similar ones (contradictions are usually the closest pairs) instead of
    # whichever happened to be generated first.
    scored_pairs.sort(key=lambda t: t[0])
    pairs: list[tuple[Memory, Memory]] = [(n, o) for _, n, o in scored_pairs[:_MAX_PAIRS_PER_BATCH]]

    if not pairs:
        return {"pairs_checked": 0, "superseded": [], "llm_calls": 0}

    # --- ONE cheap confirmation call for the whole batch ---
    listing = "\n".join(
        f"{i}. NEW: {new.content}\n   OLD: {old.content}"
        for i, (new, old) in enumerate(pairs, start=1)
    )
    data = client.chat_json(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": listing},
        ],
        cheap=cheap,
    )

    chosen = data.get("supersede", []) if isinstance(data, dict) else []
    superseded: list[dict] = []
    seen_old: set[int] = set()
    for idx in chosen:
        try:
            new, old = pairs[int(idx) - 1]
        except (TypeError, ValueError, IndexError):
            continue  # ignore hallucinated pair numbers
        if old.id in seen_old or old.status != MemStatus.active:
            continue
        old.status = MemStatus.archived
        old.superseded_by = new.id
        seen_old.add(old.id)
        superseded.append({"id": old.id, "content": old.content, "superseded_by": new.id})

    return {"pairs_checked": len(pairs), "superseded": superseded, "llm_calls": 1}
