"""Tests for presentation helpers (Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.filtering.filter_service import filter_candidates
from app.ingestion.loader import load_restaurants
from app.llm.prompt_builder import build_prompt
from app.models import (
    BudgetPreference,
    NoResultsResponse,
    RecommendationMeta,
    RecommendationResult,
    UserPreferences,
)
from app.orchestrator import recommend
from app.presentation.helpers import (
    build_preferences_from_form,
    degraded_message,
    no_results_title,
    should_show_meta,
    should_show_summary,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
E2E_FIXTURE = FIXTURES_DIR / "e2e_restaurants.json"


@pytest.fixture
def loaded_e2e():
    rows = json.loads(E2E_FIXTURE.read_text(encoding="utf-8"))
    load_restaurants(raw_df=pd.DataFrame(rows), force_reload=True)


class TestPresentationHelpers:
    def test_build_preferences_includes_additional(self):
        prefs = build_preferences_from_form(
            location="Bangalore",
            budget="medium",
            cuisine="Italian",
            min_rating=4.0,
            additional_preferences="  rooftop seating  ",
        )
        assert prefs.additional_preferences == "rooftop seating"
        assert prefs.top_n == 5

    def test_build_preferences_strips_empty_additional(self):
        prefs = build_preferences_from_form(
            location="Delhi",
            budget="low",
            cuisine="Indian",
            min_rating=3.5,
            additional_preferences="   ",
        )
        assert prefs.additional_preferences is None

    def test_should_show_summary(self):
        assert should_show_summary("Hello")
        assert not should_show_summary(None)
        assert not should_show_summary("  ")

    def test_should_show_meta_only_for_success_with_candidates(self):
        success = RecommendationResult(
            preferences=UserPreferences(
                location="X",
                budget=BudgetPreference.MEDIUM,
                cuisine="Y",
                min_rating=4.0,
            ),
            meta=RecommendationMeta(candidates_considered=10, top_n=5),
        )
        no_results = NoResultsResponse(message="No match")
        assert should_show_meta(success)
        assert not should_show_meta(no_results)

    def test_degraded_message_known_reason(self):
        meta = RecommendationMeta(degraded=True, degraded_reason="llm_api_error")
        msg = degraded_message(meta)
        assert msg is not None
        assert "AI ranking" in msg

    def test_no_results_title_is_user_facing(self):
        response = NoResultsResponse(
            message="No restaurants match your preferences in Nowhere.",
            suggestions=["Try a different city"],
        )
        title = no_results_title(response)
        assert "No restaurants match" in title
        assert "Traceback" not in title


class TestAdditionalPreferencesInPrompt:
    def test_additional_preferences_appear_in_prompt(self, loaded_e2e):
        prefs = UserPreferences(
            location="Bangalore",
            budget=BudgetPreference.MEDIUM,
            cuisine="Italian",
            min_rating=4.0,
            additional_preferences="family-friendly rooftop",
        )
        batch = filter_candidates(prefs)
        prompt = build_prompt(batch)
        assert "family-friendly rooftop" in prompt


class TestUINoMatchFlow:
    def test_no_match_returns_helpful_message_not_exception(
        self, loaded_e2e, mock_llm_env
    ):
        response = recommend(
            UserPreferences(
                location="NonexistentCityXYZ",
                budget=BudgetPreference.MEDIUM,
                cuisine="Italian",
                min_rating=4.0,
            ),
            skip_load=True,
        )
        assert isinstance(response, NoResultsResponse)
        message = no_results_title(response)
        assert "No restaurants match" in message
        assert len(response.suggestions) >= 1
