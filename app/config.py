"""Central configuration, loaded from environment / .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Qwen Cloud (DashScope international, OpenAI-compatible) ---
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_chat_model: str = "qwen-plus"
    qwen_cheap_model: str = "qwen-turbo"
    qwen_embed_model: str = "text-embedding-v4"
    embed_dim: int = 1024

    # --- Database ---
    database_url: str = "postgresql+psycopg://mnemo:mnemo@localhost:5432/mnemo"

    # --- Memory tuning ---
    decay_tau_days: float = 14.0
    forget_threshold: float = 0.15
    consolidate_similarity: float = 0.86
    default_token_budget: int = 1200

    # Hybrid retrieval weights (need not sum to 1; combined score is a weighted sum)
    w_semantic: float = 0.55
    w_keyword: float = 0.20
    w_recency: float = 0.10
    w_importance: float = 0.15


@lru_cache
def get_settings() -> Settings:
    return Settings()
