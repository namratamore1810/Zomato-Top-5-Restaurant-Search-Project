"""Parser and hydration logic for LLM recommendations."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models import (
    CandidateBatch,
    RecommendationItem,
    RecommendationMeta,
    RecommendationResult,
)

logger = logging.getLogger(__name__)


class LLMRecommendationItem(BaseModel):
    """Temporary model representing a single recommendation returned by the LLM."""

    restaurant_id: str
    rank: int
    explanation: str

    @field_validator("restaurant_id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: Any) -> str:
        return str(v).strip()

    @field_validator("rank", mode="before")
    @classmethod
    def coerce_rank_to_int(cls, v: Any) -> int:
        try:
            return int(v)
        except (ValueError, TypeError):
            # Fallback rank that will be sorted to the end
            return 999


class LLMRecommendationPayload(BaseModel):
    """Temporary model representing the full JSON payload returned by the LLM."""

    summary: str | None = None
    recommendations: list[LLMRecommendationItem] = Field(
        default_factory=list
    )


def parse_llm_response(response_text: str) -> LLMRecommendationPayload:
    """
    Clean and parse the raw LLM string response into LLMRecommendationPayload.
    """
    cleaned = response_text.strip()

    # Strip markdown code blocks (e.g. ```json ... ```)
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM response as JSON: %s", exc)
        raise exc

    # Parse and validate with Pydantic
    payload = LLMRecommendationPayload.model_validate(data)

    # Clean up and re-index ranks to ensure they are 1..N and contiguous
    # Sort recommendations by their stated rank (putting 999 or <=0 at the end)
    sorted_items = list(payload.recommendations)
    sorted_items.sort(key=lambda x: x.rank if x.rank > 0 else float("inf"))

    # Renumber sequentially
    for idx, item in enumerate(sorted_items):
        item.rank = idx + 1

    payload.recommendations = sorted_items
    return payload


def hydrate_recommendations(
    payload: LLMRecommendationPayload,
    batch: CandidateBatch,
) -> RecommendationResult:
    """
    Merge the LLM-derived ranks and explanations with canonical restaurant data.

    Enforces that:
    1. Only candidates present in CandidateBatch are returned (drops hallucinations).
    2. No duplicate restaurant IDs are recommended.
    3. If fewer recommendations than top_n are present, backfills from candidates.
    4. Truncates final recommendation list to exactly top_n.
    """
    candidate_map = {c.id: c for c in batch.candidates}
    seen_ids: set[str] = set()
    recommendations: list[RecommendationItem] = []
    rank_counter = 1

    llm_had_valid_items = False

    # Process LLM recommendations
    for item in payload.recommendations:
        r_id = item.restaurant_id
        if r_id not in candidate_map:
            logger.warning(
                "LLM returned hallucinated or filtered-out restaurant ID: %s",
                r_id,
            )
            continue
        if r_id in seen_ids:
            logger.warning(
                "LLM returned duplicate restaurant ID: %s", r_id
            )
            continue

        seen_ids.add(r_id)
        llm_had_valid_items = True
        restaurant = candidate_map[r_id]

        explanation = item.explanation.strip() if item.explanation else ""
        if not explanation:
            explanation = (
                f"Matches your preferences for {batch.preferences.cuisine} "
                f"in {batch.preferences.location}."
            )

        cost_str = (
            f"₹{restaurant.cost:.0f} for two"
            if restaurant.cost is not None
            else "Not available"
        )

        rec_item = RecommendationItem(
            rank=rank_counter,
            restaurant_id=restaurant.id,
            name=restaurant.name,
            cuisine=", ".join(restaurant.cuisines),
            rating=restaurant.rating,
            estimated_cost=cost_str,
            explanation=explanation,
            budget_tier=restaurant.budget_tier.value if hasattr(restaurant.budget_tier, 'value') else str(restaurant.budget_tier),
        )
        recommendations.append(rec_item)
        rank_counter += 1

        if len(recommendations) >= batch.preferences.top_n:
            break

    # Check if we need to backfill (LLM returned too few recommendations)
    is_degraded = False
    degraded_reason = None

    target_top_n = min(batch.preferences.top_n, len(batch.candidates))

    if len(recommendations) < target_top_n:
        is_degraded = True
        degraded_reason = "partial_llm_response"
        logger.warning(
            "LLM returned %d items, but expected %d. Backfilling from candidate batch.",
            len(recommendations),
            target_top_n,
        )

        for candidate in batch.candidates:
            if candidate.id not in seen_ids:
                explanation = (
                    f"Matches your preferences for {batch.preferences.cuisine} "
                    f"in {batch.preferences.location}."
                )
                cost_str = (
                    f"₹{candidate.cost:.0f} for two"
                    if candidate.cost is not None
                    else "Not available"
                )

                rec_item = RecommendationItem(
                    rank=rank_counter,
                    restaurant_id=candidate.id,
                    name=candidate.name,
                    cuisine=", ".join(candidate.cuisines),
                    rating=candidate.rating,
                    estimated_cost=cost_str,
                    explanation=explanation,
                    budget_tier=candidate.budget_tier.value if hasattr(candidate.budget_tier, 'value') else str(candidate.budget_tier),
                )
                recommendations.append(rec_item)
                seen_ids.add(candidate.id)
                rank_counter += 1

                if len(recommendations) >= target_top_n:
                    break

    # If the LLM returned absolutely zero valid items, mark as degraded
    if not llm_had_valid_items and target_top_n > 0:
        is_degraded = True
        degraded_reason = "llm_parsing_failed"

    meta = RecommendationMeta(
        candidates_considered=len(batch.candidates),
        top_n=batch.preferences.top_n,
        degraded=is_degraded,
        degraded_reason=degraded_reason,
    )

    return RecommendationResult(
        status="success",
        summary=payload.summary,
        preferences=batch.preferences,
        recommendations=recommendations,
        meta=meta,
    )
