"""Unit tests for the filter service (Phase 2)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest

from app.filtering.filter_service import (
  build_no_results_response,
  filter,
  filter_candidates,
  serialize_candidates,
)
from app.ingestion.loader import load_restaurants
from app.ingestion.store import reset_store
from app.models import BudgetPreference, UserPreferences
from config.settings import Settings, get_settings


@pytest.fixture
def loaded_restaurants(sample_dataframe: pd.DataFrame) -> None:
  load_restaurants(raw_df=sample_dataframe, force_reload=True)


def _settings_with(**overrides) -> Settings:
  base = get_settings()
  return Settings(
    hf_dataset_id=overrides.get("hf_dataset_id", base.hf_dataset_id),
    hf_load_retries=overrides.get("hf_load_retries", base.hf_load_retries),
    hf_load_retry_delay_sec=overrides.get(
      "hf_load_retry_delay_sec", base.hf_load_retry_delay_sec
    ),
    max_candidates=overrides.get("max_candidates", base.max_candidates),
    default_top_n=overrides.get("default_top_n", base.default_top_n),
    fallback_relaxation=overrides.get(
      "fallback_relaxation", base.fallback_relaxation
    ),
    llm_provider=overrides.get("llm_provider", base.llm_provider),
    llm_model=overrides.get("llm_model", base.llm_model),
    llm_temperature=overrides.get("llm_temperature", base.llm_temperature),
    groq_api_key=overrides.get("groq_api_key", base.groq_api_key),
  )


def test_filter_exact_match(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="Chinese",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)

  assert not batch.filter_stats.relaxed
  assert batch.filter_stats.total_after == 2
  assert len(batch.candidates) == 2
  names = {r.name for r in batch.candidates}
  assert names == {"Jalsa", "Spice Elephant"}


def test_filter_alias_matches_filter_candidates(loaded_restaurants):
  prefs = UserPreferences(
    location="delhi",
    budget=BudgetPreference.MEDIUM,
    cuisine="Italian",
    min_rating=4.0,
  )
  assert filter(prefs).candidates[0].name == filter_candidates(prefs).candidates[0].name


def test_filter_location_synonyms_and_case(loaded_restaurants):
  prefs = UserPreferences(
    location="bengaluru",
    budget=BudgetPreference.MEDIUM,
    cuisine="CHINESE",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)
  assert len(batch.candidates) == 2


def test_filter_cuisine_substring(loaded_restaurants):
  prefs = UserPreferences(
    location="delhi",
    budget=BudgetPreference.MEDIUM,
    cuisine="pizza",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)
  assert len(batch.candidates) == 1
  assert batch.candidates[0].name == "Onesta"


def test_filter_multiple_cuisines_or_match(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="Thai, French",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)
  assert len(batch.candidates) == 1
  assert batch.candidates[0].name == "Spice Elephant"


def test_filter_rating_inclusive_boundary(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="Chinese",
    min_rating=4.1,
  )
  assert len(filter_candidates(prefs).candidates) == 2

  prefs_strict = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="Chinese",
    min_rating=4.11,
  )
  assert len(filter_candidates(prefs_strict).candidates) == 0


def test_filter_budget_matching(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.HIGH,
    cuisine="Italian",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)
  assert len(batch.candidates) == 1
  assert batch.candidates[0].name == "Premium Dine"


def test_filter_sorting_and_capping(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="North Indian",
    min_rating=3.0,
  )

  mock_settings = _settings_with(max_candidates=1)
  with patch("app.filtering.filter_service.settings", mock_settings):
    batch = filter_candidates(prefs)

  assert len(batch.candidates) == 1
  assert batch.candidates[0].name == "Jalsa"
  assert batch.filter_stats.total_after == 2


def test_filter_candidates_capped_at_max(loaded_restaurants):
  mock_settings = _settings_with(max_candidates=30)
  with patch("app.filtering.filter_service.settings", mock_settings):
    batch = filter_candidates(
      UserPreferences(
        location="Bangalore",
        budget=BudgetPreference.MEDIUM,
        cuisine="North Indian",
        min_rating=3.0,
      )
    )
  assert len(batch.candidates) <= 30


def test_serialized_for_prompt_is_valid_json(loaded_restaurants):
  batch = filter_candidates(
    UserPreferences(
      location="Bangalore",
      budget=BudgetPreference.MEDIUM,
      cuisine="Chinese",
      min_rating=4.0,
    )
  )
  data = json.loads(batch.serialized_for_prompt)
  assert isinstance(data, list)
  assert data[0]["id"] == batch.candidates[0].id


def test_filter_relaxation_cuisine(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="French",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)

  assert batch.filter_stats.relaxed
  assert batch.filter_stats.relaxed_rules == ["cuisine"]
  assert len(batch.candidates) == 2


def test_filter_relaxation_budget(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.LOW,
    cuisine="Italian",
    min_rating=4.0,
  )
  batch = filter_candidates(prefs)

  assert batch.filter_stats.relaxed
  assert batch.filter_stats.relaxed_rules == ["budget"]
  assert batch.candidates[0].name == "Premium Dine"


def test_filter_no_results_even_after_relaxation(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.LOW,
    cuisine="Mexican",
    min_rating=4.5,
  )
  batch = filter_candidates(prefs)

  assert len(batch.candidates) == 0
  assert batch.filter_stats.total_after == 0


def test_filter_relaxation_disabled(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="French",
    min_rating=4.0,
  )
  mock_settings = _settings_with(fallback_relaxation=False)
  with patch("app.filtering.filter_service.settings", mock_settings):
    batch = filter_candidates(prefs)

  assert not batch.filter_stats.relaxed
  assert len(batch.candidates) == 0


def test_build_no_results_response(loaded_restaurants):
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.LOW,
    cuisine="Mexican",
    min_rating=4.5,
  )
  batch = filter_candidates(prefs)
  response = build_no_results_response(prefs, batch.filter_stats)

  assert response.status == "no_results"
  assert "Bangalore" in response.message
  assert response.suggestions


def test_filter_store_not_loaded():
  reset_store()
  prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="Italian",
    min_rating=4.0,
  )

  with pytest.raises(RuntimeError, match="not loaded"):
    filter_candidates(prefs)


def test_serialize_candidates_standalone(loaded_restaurants):
  batch = filter_candidates(
    UserPreferences(
      location="delhi",
      budget=BudgetPreference.MEDIUM,
      cuisine="Italian",
      min_rating=4.0,
    )
  )
  text = serialize_candidates(batch.candidates)
  assert json.loads(text)[0]["name"] == "Onesta"
