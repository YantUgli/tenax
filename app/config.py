"""Central configuration, loaded from environment / .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Qwen Cloud (DashScope international, OpenAI-compatible) ---
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    # qwen-plus free-tier quota is permanently exhausted, so the default chat model is
    # qwen-turbo (a live model). Non-cheap paths (reflect, remember without --cheap) would
    # otherwise 403 on every call.
    qwen_chat_model: str = "qwen-turbo"
    qwen_cheap_model: str = "qwen-turbo"
    qwen_embed_model: str = "text-embedding-v4"
    embed_dim: int = 1024

    # --- Database ---
    database_url: str = "postgresql+psycopg://tenax:tenax@localhost:5432/tenax"

    # --- Memory tuning ---
    decay_tau_days: float = 14.0
    forget_threshold: float = 0.15
    consolidate_similarity: float = 0.86
    default_token_budget: int = 1200

    # Belief revision (write-time contradiction handling). A new fact whose embedding is
    # at least `revise_similarity` cosine-similar to a stored active fact is a candidate
    # for superseding it. Calibrated on text-embedding-v4: genuine "same attribute, new
    # value" pairs measure ~0.55-0.70 while unrelated facts sit ~0.35, so the band starts
    # at 0.50 — recall of candidates lives here, precision lives in the LLM confirmation.
    revise_enabled: bool = True
    revise_similarity: float = 0.50

    # Budget packing: Maximal Marginal Relevance. Greedy top-score packing lets a cluster
    # of near-duplicate (or merely topic-adjacent) memories eat the budget, which starves
    # multi-fact questions of their second fact — measured on LongMemEval temporal items,
    # where "Buffalo Wild Wings" crowded out "Buffalo Bills". Each pick maximises
    #   lambda * relevance - (1 - lambda) * max_similarity_to_already_selected
    # lambda = 1.0 reproduces pure-relevance packing exactly, and is the default: measured
    # at 0.7 on the 13 pinned temporal items it recovered no missing gold fact (the facts
    # lose on semantic+recency score, not on redundancy), so the knob ships inert until
    # there is evidence for a different value.
    mmr_lambda: float = 1.0

    # Hybrid retrieval weights (need not sum to 1; combined score is a weighted sum)
    w_semantic: float = 0.55
    w_keyword: float = 0.20
    w_recency: float = 0.10
    w_importance: float = 0.15


@lru_cache
def get_settings() -> Settings:
    return Settings()
