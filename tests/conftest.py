"""Shared pytest fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from app.ingestion.store import reset_store
from config.settings import clear_settings_cache

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clear_restaurant_store():
  reset_store()
  yield
  reset_store()


@pytest.fixture
def sample_raw_rows() -> list[dict]:
  path = FIXTURES_DIR / "sample_restaurants.json"
  return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def sample_dataframe(sample_raw_rows: list[dict]) -> pd.DataFrame:
  return pd.DataFrame(sample_raw_rows)


@pytest.fixture
def mock_llm_json() -> str:
  """Valid LLM rank/explain payload for unit tests (no Groq API)."""
  path = FIXTURES_DIR / "mock_llm_rank_response.json"
  return path.read_text(encoding="utf-8")


@pytest.fixture
def mock_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
  """Force mock LLM provider so CI never calls Groq."""
  monkeypatch.setenv("LLM_PROVIDER", "mock")
  monkeypatch.delenv("GROQ_API_KEY", raising=False)
  clear_settings_cache()
  yield
  clear_settings_cache()
