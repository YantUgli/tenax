"""Thin wrapper around the OpenAI SDK pointed at Qwen Cloud (DashScope-intl).

The Qwen Cloud API is OpenAI-compatible, so we reuse the official ``openai`` client
and only swap ``base_url`` + ``api_key``. This module centralizes chat, JSON-mode
chat, and embeddings, with basic retry/backoff so the memory engine stays clean.
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


class QwenClient:
    def __init__(self) -> None:
        s = get_settings()
        if not s.qwen_api_key:
            raise RuntimeError(
                "QWEN_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._settings = s
        self._client = OpenAI(api_key=s.qwen_api_key, base_url=s.qwen_base_url)

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
        back to best-effort extraction if the model wraps the JSON in prose."""
        model = model or (self._settings.qwen_cheap_model if cheap else self._settings.qwen_chat_model)
        resp = self._with_retry(
            lambda: self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        )
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
            out.extend(d.embedding for d in resp.data)
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _with_retry(fn):
        last: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - surface after retries
                last = exc
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Qwen API call failed after {_MAX_RETRIES} retries: {last}")


def _loads_lenient(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = min((i for i in (content.find("{"), content.find("[")) if i != -1), default=-1)
        end = max(content.rfind("}"), content.rfind("]"))
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start : end + 1])
        raise
