"""FastAPI REST surface for Mnemo.

Powers the Streamlit demo and, once deployed to Alibaba Cloud ECS, is the public
backend the judges hit (satisfying the "backend running on Alibaba Cloud" requirement).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.db import init_db

log = logging.getLogger("mnemo")


@lru_cache
def _engine():
    # Imported lazily so the process (and /health) starts even without a Qwen key.
    from app.memory.engine import MemoryEngine

    return MemoryEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - don't block startup if DB is warming up
        log.warning("init_db skipped at startup: %s", exc)
    yield


app = FastAPI(title="Mnemo", version="0.1.0", lifespan=lifespan)


# ------------------------------------------------------------------ schemas
class RememberIn(BaseModel):
    user_id: str = "default"
    text: str
    source: str | None = None


class RecallIn(BaseModel):
    user_id: str = "default"
    query: str
    token_budget: int | None = None


class UserIn(BaseModel):
    user_id: str = "default"
    threshold: float | None = None


# ----------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    return {"status": "ok", "model": get_settings().qwen_chat_model}


@app.post("/remember")
def remember(body: RememberIn):
    try:
        return _engine().remember(body.user_id, body.text, source=body.source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/recall")
def recall(body: RecallIn):
    try:
        return _engine().recall(body.user_id, body.query, token_budget=body.token_budget)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/forget")
def forget(body: UserIn):
    return _engine().forget(body.user_id, threshold=body.threshold)


@app.post("/reflect")
def reflect(body: UserIn):
    return _engine().reflect(body.user_id, threshold=body.threshold)


@app.get("/memories")
def memories(user_id: str = "default", status: str = "active", limit: int = 100):
    return _engine().list_memories(user_id, status=status, limit=limit)


@app.get("/stats")
def stats(user_id: str = "default"):
    return _engine().stats(user_id)
