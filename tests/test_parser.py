"""Unit tests for the LLM response parser, hydration, and recommendation engine (Phase 3)."""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from app.llm.engine import generate_recommendations
from app.llm.parser import hydrate_recommendations, parse_llm_response
from app.models import (
    BudgetPreference,
    BudgetTier,
    CandidateBatch,
    Restaurant,
    UserPreferences,
)


@pytest.fixture
def sample_candidates() -> list[Restaurant]:
    return [
        Restaurant(
            id="res1",
            name="Cafe Italy",
            location="bangalore",
            cuisines=["Italian"],
            rating=4.5,
            cost=600.0,
            budget_tier=BudgetTier.MEDIUM,
        ),
        Restaurant(
            id="res2",
            name="Pizza Corner",
            location="bangalore",
            cuisines=["Pizza", "Italian"],
            rating=4.2,
            cost=400.0,
            budget_tier=BudgetTier.MEDIUM,
        ),
        Restaurant(
            id="res3",
            name="Pasta House",
            location="bangalore",
            cuisines=["Italian"],
            rating=4.0,
            cost=800.0,
            budget_tier=BudgetTier.MEDIUM,
        ),
    ]


@pytest.fixture
def candidate_batch(sample_candidates) -> CandidateBatch:
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetPreference.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
        top_n=3,
    )
    return CandidateBatch(
        preferences=prefs,
        candidates=sample_candidates,
        serialized_for_prompt="[]",
    )


class TestParser:
    def test_parse_valid_json(self):
        raw = """{
            "summary": "This is a summary.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "Fits well"},
                {"restaurant_id": "res2", "rank": 2, "explanation": "Also fits"}
            ]
        }"""
        payload = parse_llm_response(raw)
        assert payload.summary == "This is a summary."
        assert len(payload.recommendations) == 2
        assert payload.recommendations[0].restaurant_id == "res1"
        assert payload.recommendations[0].rank == 1
        assert payload.recommendations[1].rank == 2

    def test_parse_json_wrapped_in_markdown(self):
        raw = """```json
        {
            "summary": "Fenced summary.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "Fenced fits"}
            ]
        }
        ```"""
        payload = parse_llm_response(raw)
        assert payload.summary == "Fenced summary."
        assert len(payload.recommendations) == 1
        assert payload.recommendations[0].restaurant_id == "res1"

    def test_parse_type_coercion(self):
        raw = """{
            "summary": "Coercion test.",
            "recommendations": [
                {"restaurant_id": 12345, "rank": "1", "explanation": "Coerced"}
            ]
        }"""
        payload = parse_llm_response(raw)
        assert payload.recommendations[0].restaurant_id == "12345"
        assert payload.recommendations[0].rank == 1

    def test_parse_duplicate_and_gap_ranks(self):
        # Two rank 1s, and a gap to rank 5
        raw = """{
            "summary": "Renumbering test.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "First"},
                {"restaurant_id": "res2", "rank": 1, "explanation": "Second"},
                {"restaurant_id": "res3", "rank": 5, "explanation": "Third"}
            ]
        }"""
        payload = parse_llm_response(raw)
        assert len(payload.recommendations) == 3
        # Should be re-indexed to contiguous ranks starting at 1
        assert payload.recommendations[0].rank == 1
        assert payload.recommendations[1].rank == 2
        assert payload.recommendations[2].rank == 3

    def test_parse_invalid_json_raises(self):
        raw = "Not a JSON string at all"
        with pytest.raises(json.JSONDecodeError):
            parse_llm_response(raw)


class TestHydration:
    def test_hydration_success(self, candidate_batch):
        raw = """{
            "summary": "Enjoy Italian food.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "Authentic pasta"},
                {"restaurant_id": "res2", "rank": 2, "explanation": "Great pizza"}
            ]
        }"""
        payload = parse_llm_response(raw)
        result = hydrate_recommendations(payload, candidate_batch)

        assert result.status == "success"
        assert result.summary == "Enjoy Italian food."
        assert not result.meta.degraded
        assert len(result.recommendations) == 2

        # Check fields hydrated from canonical dataset
        rec1 = result.recommendations[0]
        assert rec1.rank == 1
        assert rec1.restaurant_id == "res1"
        assert rec1.name == "Cafe Italy"
        assert rec1.cuisine == "Italian"
        assert rec1.rating == 4.5
        assert rec1.estimated_cost == "₹600 for two"
        assert rec1.explanation == "Authentic pasta"

    def test_hydration_drops_hallucinations_and_duplicates(
        self, candidate_batch
    ):
        raw = """{
            "summary": "Filtering hallucinations.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "Valid"},
                {"restaurant_id": "res_fake", "rank": 2, "explanation": "Hallucinated"},
                {"restaurant_id": "res1", "rank": 3, "explanation": "Duplicate"}
            ]
        }"""
        payload = parse_llm_response(raw)
        result = hydrate_recommendations(payload, candidate_batch)

        # Expected behavior:
        # res1 included. res_fake dropped. Duplicate res1 dropped.
        # Target top_n is 3. Since only 1 is valid, it will backfill res2 and res3!
        # Thus the final recommendations count will be 3, but marked degraded due to partial response.
        assert result.meta.degraded
        assert result.meta.degraded_reason == "partial_llm_response"
        assert len(result.recommendations) == 3
        # First item is the valid LLM choice
        assert result.recommendations[0].restaurant_id == "res1"
        # Others are backfilled from candidate list
        assert result.recommendations[1].restaurant_id == "res2"
        assert result.recommendations[2].restaurant_id == "res3"

    def test_hydration_truncation_to_top_n(self, candidate_batch):
        # top_n is 3. LLM returns 4.
        # Should truncate to 3.
        candidate_batch.preferences.top_n = 2
        raw = """{
            "summary": "Truncate test.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "One"},
                {"restaurant_id": "res2", "rank": 2, "explanation": "Two"},
                {"restaurant_id": "res3", "rank": 3, "explanation": "Three"}
            ]
        }"""
        payload = parse_llm_response(raw)
        result = hydrate_recommendations(payload, candidate_batch)

        assert len(result.recommendations) == 2
        assert result.recommendations[0].restaurant_id == "res1"
        assert result.recommendations[1].restaurant_id == "res2"

    def test_hydration_backfill(self, candidate_batch):
        # LLM returns fewer recommendations than top_n (e.g. 1 instead of 3)
        raw = """{
            "summary": "Only one.",
            "recommendations": [
                {"restaurant_id": "res2", "rank": 1, "explanation": "Pizza"}
            ]
        }"""
        payload = parse_llm_response(raw)
        result = hydrate_recommendations(payload, candidate_batch)

        assert result.meta.degraded
        assert result.meta.degraded_reason == "partial_llm_response"
        assert len(result.recommendations) == 3

        # First is the LLM one
        assert result.recommendations[0].restaurant_id == "res2"
        # Remaining are backfilled from candidates (res1, then res3)
        assert result.recommendations[1].restaurant_id == "res1"
        assert result.recommendations[2].restaurant_id == "res3"


class TestEngineOrchestration:
    def test_generate_recommendations_mock_client_no_patch(
        self, candidate_batch, mock_llm_env
    ):
        """End-to-end with mock LLM (no Groq API key)."""
        result = generate_recommendations(candidate_batch)

        assert result.status == "success"
        assert result.summary is not None
        assert len(result.recommendations) == 3
        assert result.recommendations[0].restaurant_id == "res1"
        assert result.recommendations[0].name == "Cafe Italy"
        assert result.recommendations[0].explanation

    @patch("app.llm.client.LLMClient.complete_json")
    def test_generate_recommendations_success(
        self, mock_complete, candidate_batch
    ):
        mock_complete.return_value = """{
            "summary": "Great Italian.",
            "recommendations": [
                {"restaurant_id": "res1", "rank": 1, "explanation": "Awesome"},
                {"restaurant_id": "res2", "rank": 2, "explanation": "Delish"}
            ]
        }"""
        result = generate_recommendations(candidate_batch)

        assert result.status == "success"
        assert not result.meta.degraded
        assert len(result.recommendations) == 2
        assert result.recommendations[0].restaurant_id == "res1"

    @patch("app.llm.client.LLMClient.complete_json")
    def test_generate_recommendations_retry_success(
        self, mock_complete, candidate_batch
    ):
        # Attempt 1 returns invalid JSON; Attempt 2 returns valid JSON
        mock_complete.side_effect = [
            "Not JSON at all",
            """{
                "summary": "Retry summary",
                "recommendations": [
                    {"restaurant_id": "res1", "rank": 1, "explanation": "Retry success"}
                ]
            }""",
        ]
        result = generate_recommendations(candidate_batch)

        assert result.status == "success"
        # Note: it backfills to top_n (3), so marked degraded.
        # But it successfully parsed the retry payload (contains Retry summary).
        assert result.summary == "Retry summary"
        assert result.recommendations[0].restaurant_id == "res1"
        assert result.recommendations[0].explanation == "Retry success"

    @patch("app.llm.client.LLMClient.complete_json")
    def test_generate_recommendations_retry_exhausted_fallback(
        self, mock_complete, candidate_batch
    ):
        # Both attempts fail to parse
        mock_complete.side_effect = [
            "Invalid JSON 1",
            "Invalid JSON 2",
        ]
        result = generate_recommendations(candidate_batch)

        assert result.status == "success"
        assert result.meta.degraded
        assert result.meta.degraded_reason == "llm_parsing_failed"
        # Fallback recommendations are filled from pre-ranked candidate order
        assert len(result.recommendations) == 3
        assert result.recommendations[0].restaurant_id == "res1"
        assert (
            "Matches your preferences for Italian in Bangalore"
            in result.recommendations[0].explanation
        )

    @patch("app.llm.client.LLMClient.complete_json")
    def test_generate_recommendations_api_error_fallback(
        self, mock_complete, candidate_batch
    ):
        from app.llm.client import LLMClientError

        # API raises connection error
        mock_complete.side_effect = LLMClientError("API down")
        result = generate_recommendations(candidate_batch)

        assert result.status == "success"
        assert result.meta.degraded
        assert result.meta.degraded_reason == "llm_api_error"
        assert len(result.recommendations) == 3
        assert result.recommendations[0].restaurant_id == "res1"

    def test_generate_recommendations_empty_candidates(self):
        # Empty batch should return empty recommendations without calling LLM
        prefs = UserPreferences(
            location="Bangalore",
            budget=BudgetPreference.MEDIUM,
            cuisine="Italian",
            min_rating=4.0,
            top_n=3,
        )
        empty_batch = CandidateBatch(
            preferences=prefs,
            candidates=[],
            serialized_for_prompt="[]",
        )

        with patch(
            "app.llm.client.LLMClient.complete_json"
        ) as mock_complete:
            result = generate_recommendations(empty_batch)
            mock_complete.assert_not_called()

        assert result.status == "success"
        assert result.meta.degraded
        assert result.meta.degraded_reason == "zero_candidates"
        assert len(result.recommendations) == 0
