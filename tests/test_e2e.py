"""End-to-end tests for the recommendation orchestrator (Phase 4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from app.filtering.filter_service import filter_candidates
from app.ingestion.loader import load_restaurants
from app.models import (
    BudgetPreference,
    ErrorResponse,
    NoResultsResponse,
    RecommendationResult,
    UserPreferences,
)
from app.orchestrator import recommend, validate_preferences

FIXTURES_DIR = Path(__file__).parent / "fixtures"
E2E_FIXTURE = FIXTURES_DIR / "e2e_restaurants.json"


@pytest.fixture
def e2e_dataframe() -> pd.DataFrame:
    rows = json.loads(E2E_FIXTURE.read_text(encoding="utf-8"))
    return pd.DataFrame(rows)


@pytest.fixture
def loaded_e2e(e2e_dataframe: pd.DataFrame) -> None:
    load_restaurants(raw_df=e2e_dataframe, force_reload=True)


def _default_prefs(**overrides) -> UserPreferences:
    base = {
        "location": "Bangalore",
        "budget": BudgetPreference.MEDIUM,
        "cuisine": "Italian",
        "min_rating": 4.0,
        "top_n": 5,
    }
    base.update(overrides)
    return UserPreferences(**base)


def _assert_recommendation_schema(result: RecommendationResult) -> None:
    """Architecture §6.3 final response schema."""
    assert result.status == "success"
    assert result.preferences is not None
    assert result.meta.top_n == 5
    assert result.meta.candidates_considered >= len(result.recommendations)

    required_item_fields = {
        "rank",
        "restaurant_id",
        "name",
        "cuisine",
        "rating",
        "estimated_cost",
        "explanation",
    }
    for item in result.recommendations:
        dumped = item.model_dump()
        assert required_item_fields <= set(dumped.keys())
        assert item.explanation.strip()
        assert 1 <= item.rank <= result.meta.top_n


class TestValidatePreferences:
    def test_validates_dict_input(self):
        prefs = validate_preferences(
            {
                "location": "Bangalore",
                "budget": "medium",
                "cuisine": "Italian",
                "min_rating": 4.0,
            }
        )
        assert prefs.location == "Bangalore"

    def test_rejects_empty_location(self):
        with pytest.raises(ValueError, match="location"):
            validate_preferences(
                UserPreferences(
                    location="   ",
                    budget=BudgetPreference.MEDIUM,
                    cuisine="Italian",
                    min_rating=4.0,
                )
            )

    def test_rejects_invalid_budget(self):
        with pytest.raises(Exception):
            validate_preferences(
                {
                    "location": "Bangalore",
                    "budget": "luxury",
                    "cuisine": "Italian",
                    "min_rating": 4.0,
                }
            )


class TestRecommendE2E:
    def test_e2e_returns_five_recommendations(
        self, loaded_e2e, mock_llm_env
    ):
        response = recommend(_default_prefs(), skip_load=True)

        assert isinstance(response, RecommendationResult)
        assert len(response.recommendations) == 5
        _assert_recommendation_schema(response)

    def test_all_results_are_subset_of_filtered_candidates(
        self, loaded_e2e, mock_llm_env
    ):
        prefs = _default_prefs()
        batch = filter_candidates(prefs)
        candidate_ids = {c.id for c in batch.candidates}

        response = recommend(prefs, skip_load=True)
        assert isinstance(response, RecommendationResult)

        for item in response.recommendations:
            assert item.restaurant_id in candidate_ids

    def test_zero_candidates_skips_llm(self, loaded_e2e, mock_llm_env):
        prefs = _default_prefs(
            location="NonexistentCityXYZ",
            cuisine="Italian",
        )

        with patch("app.orchestrator.generate_recommendations") as mock_llm:
            response = recommend(prefs, skip_load=True)
            mock_llm.assert_not_called()

        assert isinstance(response, NoResultsResponse)
        assert response.status == "no_results"
        assert "No restaurants match" in response.message

    def test_no_results_includes_suggestions(
        self, loaded_e2e, mock_llm_env
    ):
        response = recommend(
            _default_prefs(location="NonexistentCityXYZ"),
            skip_load=True,
        )
        assert isinstance(response, NoResultsResponse)
        assert len(response.suggestions) >= 1

    def test_validation_error_returns_error_response(self, mock_llm_env):
        response = recommend(
            {
                "location": "Bangalore",
                "budget": "invalid_budget",
                "cuisine": "Italian",
                "min_rating": 4.0,
            }
        )
        assert isinstance(response, ErrorResponse)
        assert response.code == "validation_error"

    def test_dataset_load_failure_returns_error_response(
        self, monkeypatch, mock_llm_env
    ):
        from app.ingestion.loader import DatasetLoadError

        def _fail_load(**_kwargs):
            raise DatasetLoadError("simulated HF failure")

        monkeypatch.setattr(
            "app.orchestrator.load_restaurants", _fail_load
        )
        response = recommend(_default_prefs())

        assert isinstance(response, ErrorResponse)
        assert response.code == "dataset_load_failed"
        assert "Unable to load" in response.message

    def test_summary_supported_with_mock_llm(self, loaded_e2e, mock_llm_env):
        response = recommend(_default_prefs(), skip_load=True)
        assert isinstance(response, RecommendationResult)
        assert response.summary is not None
