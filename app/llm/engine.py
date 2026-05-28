"""Orchestration engine for prompt compilation, LLM calls, retries, and fallbacks."""

from __future__ import annotations

import json
import logging

import pydantic

from app.llm.client import LLMClient, LLMClientError
from app.llm.parser import hydrate_recommendations, parse_llm_response
from app.llm.prompt_builder import build_prompt
from app.models import (
    CandidateBatch,
    RecommendationItem,
    RecommendationMeta,
    RecommendationResult,
)

logger = logging.getLogger(__name__)


def _get_fallback_result(
    batch: CandidateBatch, reason: str
) -> RecommendationResult:
    """
    Construct a degraded fallback result using pre-ranked candidate order
    and template explanations.
    """
    recommendations: list[RecommendationItem] = []
    prefs = batch.preferences
    target_top_n = min(prefs.top_n, len(batch.candidates))

    for idx, candidate in enumerate(batch.candidates[:target_top_n]):
        cost_str = (
            f"₹{candidate.cost:.0f} for two"
            if candidate.cost is not None
            else "Not available"
        )
        explanation = (
            f"Matches your preferences for {prefs.cuisine} in {prefs.location}."
        )

        rec_item = RecommendationItem(
            rank=idx + 1,
            restaurant_id=candidate.id,
            name=candidate.name,
            cuisine=", ".join(candidate.cuisines),
            rating=candidate.rating,
            estimated_cost=cost_str,
            explanation=explanation,
            budget_tier=candidate.budget_tier.value if hasattr(candidate.budget_tier, 'value') else str(candidate.budget_tier),
        )
        recommendations.append(rec_item)

    meta = RecommendationMeta(
        candidates_considered=len(batch.candidates),
        top_n=prefs.top_n,
        degraded=True,
        degraded_reason=reason,
    )

    return RecommendationResult(
        status="success",
        summary=None,
        preferences=prefs,
        recommendations=recommendations,
        meta=meta,
    )


def generate_recommendations(batch: CandidateBatch) -> RecommendationResult:
    """
    Generate restaurant recommendations using LLM.
    Implements 1 retry on malformed JSON and a fallback path for errors.
    """
    # Safety check: if no candidates, return empty fallback result directly
    if not batch.candidates:
        logger.info(
            "Candidate list is empty. Returning empty fallback response."
        )
        return _get_fallback_result(batch, reason="zero_candidates")

    client = LLMClient()
    prompt = build_prompt(batch)

    # Attempt 1
    try:
        response_text = client.complete_json(prompt)
        payload = parse_llm_response(response_text)
        return hydrate_recommendations(payload, batch)
    except (json.JSONDecodeError, pydantic.ValidationError, ValueError) as exc:
        logger.warning(
            "Attempt 1: Malformed JSON or schema validation error. Retrying... Error: %s",
            exc,
        )
        # Attempt 2 (Retry once)
        try:
            response_text = client.complete_json(prompt)
            payload = parse_llm_response(response_text)
            return hydrate_recommendations(payload, batch)
        except Exception as retry_exc:
            logger.error(
                "Attempt 2 failed. Falling back to pre-ranked candidates. Error: %s",
                retry_exc,
            )
            return _get_fallback_result(batch, reason="llm_parsing_failed")
    except LLMClientError as exc:
        logger.error(
            "LLM API client failed. Falling back to pre-ranked candidates. Error: %s",
            exc,
        )
        return _get_fallback_result(batch, reason="llm_api_error")
    except Exception as exc:
        logger.error(
            "Unexpected error in recommendation engine: %s. Falling back.", exc
        )
        return _get_fallback_result(batch, reason="unexpected_error")
