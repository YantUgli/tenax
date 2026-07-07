"""Thin wrapper around the OpenAI SDK pointed at Qwen Cloud (DashScope-intl).

The Qwen Cloud API is OpenAI-compatible, so we reuse the official ``openai`` client
and only swap ``base_url`` + ``api_key``. This module centralizes chat, JSON-mode
chat, and embeddings, with basic retry/backoff so the memory engine stays clean.

Free-tier awareness (Langkah 2): every model carries a ~1M token quota. This client
therefore (a) accumulates per-modality token usage so a run can report how close it is
to the ceiling, (b) raises :class:`QuotaExceeded` — a *terminal* error, distinct from a
transient rate limit — so a long benchmark can checkpoint and stop cleanly instead of
crashing, and (c) optionally rotates the *extraction* model (the ``chat_json`` path) to
the next model in a curated pool when one runs out. Reader, judge, and embedding models
are never rotated: their consistency is what the benchmark measures.
"""
from __future__ import annotations

import json
import time
from typing import Any

from openai import OpenAI

from app.config import get_settings

# DashScope caps embedding batch size; stay well under it.
_EMBED_BATCH = 10
_MAX_RETRIES = 4


class QuotaExceeded(RuntimeError):
    """A model's free-tier token quota is exhausted — terminal, not a transient rate limit.

    The caller (benchmark harness) treats this as a signal to checkpoint and stop, rather
    than retry: retrying an exhausted quota only wastes wall-clock time.
    """


def _is_quota_error(exc: Exception) -> bool:
    """True if ``exc`` looks like hard quota exhaustion (terminal) vs. transient throttling.

    We classify as terminal only when the message mentions *quota* alongside an
    exhaustion word. Pure rate-limit messages ("requests per minute", "Throttling")
    contain neither and stay retryable.
    """
    msg = str(exc).lower()
    if "insufficient_quota" in msg:
        return True
    if "quota" in msg and any(k in msg for k in ("exceed", "exhaust", "insufficient", "allocat", "run out")):
        return True
    return False


class QwenClient:
    def __init__(self) -> None:
        s = get_settings()
        if not s.qwen_api_key:
            raise RuntimeError(
                "QWEN_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._settings = s
        self._client = OpenAI(api_key=s.qwen_api_key, base_url=s.qwen_base_url)

        # --- free-tier usage tracking (accumulated from resp.usage) ---
        self._usage = {
            "chat_prompt": 0, "chat_completion": 0, "chat_calls": 0,
            "embed_prompt": 0, "embed_calls": 0,
        }

        # --- extraction-model rotation (chat_json path only; opt-in, default OFF) ---
        self._rotate_enabled = False
        self._rotation_models: list[str] = []
        self._rotation_idx = 0

    # ---------------------------------------------------------------- rotation
    def enable_rotation(self, models: list[str]) -> None:
        """Turn on extraction-model rotation over ``models`` (in order).

        Only the ``chat_json`` path (extraction) rotates. When the current model raises
        :class:`QuotaExceeded`, the client advances to the next model and retries; when
        the pool is exhausted it re-raises. Reader/judge (``chat``) and embeddings never
        rotate. Intended purely to enlarge a retrieval-only probe under the free tier.
        """
        self._rotation_models = [m for m in models if m]
        self._rotation_idx = 0
        self._rotate_enabled = bool(self._rotation_models)

    def _rotating(self, explicit_model: str | None) -> bool:
        # rotate only when enabled and the caller did not pin an explicit model
        return self._rotate_enabled and explicit_model is None and bool(self._rotation_models)

    # ------------------------------------------------------------------ chat
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        cheap: bool = False,
    ) -> str:
        model = model or (self._settings.qwen_cheap_model if cheap else self._settings.qwen_chat_model)
        resp = self._with_retry(
            lambda: self._client.chat.completions.create(
                model=model, messages=messages, temperature=temperature
            )
        )
        self._track_chat(resp)
        return resp.choices[0].message.content or ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        cheap: bool = False,
    ) -> Any:
        """Chat that returns parsed JSON. Uses response_format json_object and falls
        back to best-effort extraction if the model wraps the JSON in prose.

        This is the extraction path; it is the only method that honours model rotation.
        """
        base = model or (self._settings.qwen_cheap_model if cheap else self._settings.qwen_chat_model)
        while True:
            use_model = self._rotation_models[self._rotation_idx] if self._rotating(model) else base
            try:
                resp = self._with_retry(
                    lambda m=use_model: self._client.chat.completions.create(
                        model=m,
                        messages=messages,
                        temperature=temperature,
                        response_format={"type": "json_object"},
                    )
                )
                break
            except QuotaExceeded:
                if self._rotating(model) and self._rotation_idx + 1 < len(self._rotation_models):
                    self._rotation_idx += 1
                    continue  # same request, next model in the pool
                raise
        self._track_chat(resp)
        content = resp.choices[0].message.content or "{}"
        return _loads_lenient(content)

    # ------------------------------------------------------------- embeddings
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts with text-embedding-v4, chunked to respect batch limits."""
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i : i + _EMBED_BATCH]
            resp = self._with_retry(
                lambda b=batch: self._client.embeddings.create(
                    model=self._settings.qwen_embed_model,
                    input=b,
                    dimensions=self._settings.embed_dim,
                    encoding_format="float",
                )
            )
            self._track_embed(resp)
            out.extend(d.embedding for d in resp.data)
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    # ------------------------------------------------------------------ usage
    def _track_chat(self, resp) -> None:
        u = getattr(resp, "usage", None)
        if u is not None:
            self._usage["chat_prompt"] += int(getattr(u, "prompt_tokens", 0) or 0)
            self._usage["chat_completion"] += int(getattr(u, "completion_tokens", 0) or 0)
        self._usage["chat_calls"] += 1

    def _track_embed(self, resp) -> None:
        u = getattr(resp, "usage", None)
        if u is not None:
            self._usage["embed_prompt"] += int(getattr(u, "prompt_tokens", 0) or 0)
        self._usage["embed_calls"] += 1

    def usage(self) -> dict:
        """Snapshot of cumulative token usage, split by modality (chat vs embed)."""
        u = dict(self._usage)
        u["chat_total"] = u["chat_prompt"] + u["chat_completion"]
        u["embed_total"] = u["embed_prompt"]
        u["rotation_model_idx"] = self._rotation_idx
        return u

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _with_retry(fn):
        last: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - surface after retries
                if _is_quota_error(exc):
                    raise QuotaExceeded(str(exc)) from exc  # terminal: do not retry
                last = exc
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Qwen API call failed after {_MAX_RETRIES} retries: {last}")


def _salvage_objects(content: str) -> list[dict]:
    """Recover the complete JSON objects from a possibly-truncated response.

    Extraction responses are ``{"memories": [ {..}, {..}, .. ]}``. When the model runs
    out of output tokens mid-array the whole string fails to parse — but the objects that
    *did* arrive are still usable. This decodes each top-level object after the opening
    ``[`` with ``raw_decode`` and drops a half-written final one, so a truncated batch
    keeps the memories it captured instead of losing all of them.
    """
    dec = json.JSONDecoder()
    lb = content.find("[")
    i, n = (lb + 1 if lb != -1 else 0), len(content)
    out: list[dict] = []
    while i < n:
        c = content.find("{", i)
        if c == -1:
            break
        try:
            obj, end = dec.raw_decode(content, c)
        except json.JSONDecodeError:
            break  # truncated/garbled from here on — keep what we have
        if isinstance(obj, dict):
            out.append(obj)
        i = end
    return out


def _loads_lenient(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = min((i for i in (content.find("{"), content.find("[")) if i != -1), default=-1)
        end = max(content.rfind("}"), content.rfind("]"))
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass
        # last resort: response was truncated mid-array — salvage complete objects.
        # A bare list is fine: callers that expect {"memories": [...]} also accept a list.
        salvaged = _salvage_objects(content)
        if salvaged:
            return salvaged
        raise
