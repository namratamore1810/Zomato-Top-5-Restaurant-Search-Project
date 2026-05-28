"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _get_setting(name: str, default: str | None = None) -> str | None:
    # 1. Try OS environment variable
    val = os.getenv(name)
    if val is not None and val.strip() != "":
        return val
    # 2. Try streamlit secrets if streamlit is installed/imported
    try:
        import streamlit as st
        # Check if secrets attribute exists and has the key
        if hasattr(st, "secrets") and st.secrets is not None:
            if name in st.secrets:
                return str(st.secrets[name])
    except Exception:
        pass
    return default


def _bool_setting(name: str, default: bool) -> bool:
    raw = _get_setting(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    hf_dataset_id: str
    hf_load_retries: int
    hf_load_retry_delay_sec: float
    max_candidates: int
    default_top_n: int
    fallback_relaxation: bool
    llm_provider: str
    llm_model: str
    llm_temperature: float
    groq_api_key: str | None


def _int_setting(name: str, default: int) -> int:
    raw = _get_setting(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_setting(name: str, default: float) -> float:
    raw = _get_setting(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@lru_cache
def get_settings() -> Settings:
    return Settings(
        hf_dataset_id=_get_setting(
            "HF_DATASET_ID", "ManikaSaini/zomato-restaurant-recommendation"
        ),
        hf_load_retries=_int_setting("HF_LOAD_RETRIES", 3),
        hf_load_retry_delay_sec=_float_setting("HF_LOAD_RETRY_DELAY_SEC", 2.0),
        max_candidates=_int_setting("MAX_CANDIDATES", 30),
        default_top_n=_int_setting("DEFAULT_TOP_N", 5),
        fallback_relaxation=_bool_setting("FALLBACK_RELAXATION", True),
        llm_provider=_get_setting("LLM_PROVIDER", "groq"),
        llm_model=_get_setting("LLM_MODEL", "llama-3.3-70b-versatile"),
        llm_temperature=_float_setting("LLM_TEMPERATURE", 0.3),
        groq_api_key=_get_setting("GROQ_API_KEY"),
    )


def clear_settings_cache() -> None:
    """Clear cached settings (for tests)."""
    get_settings.cache_clear()


settings = get_settings()
