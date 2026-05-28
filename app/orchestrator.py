"""Application orchestrator — single entry point for the recommendation pipeline (Phase 4)."""

from __future__ import annotations

import logging
import time
from typing import Any, Union

from pydantic import ValidationError

from app.filtering.filter_service import (
    build_no_results_response,
    filter_candidates,
)
from app.ingestion.loader import DatasetLoadError, load_restaurants
from app.llm.engine import generate_recommendations
from app.models import (
    ErrorResponse,
    NoResultsResponse,
    RecommendationResult,
    UserPreferences,
)

logger = logging.getLogger(__name__)

RecommendResponse = Union[
    RecommendationResult,
    NoResultsResponse,
    ErrorResponse,
]

USER_MESSAGES = {
    "dataset_load_failed": "Unable to load restaurant data. Please try again later.",
    "data_not_ready": "Unable to load restaurant data. Please try again later.",
    "validation_error": "Invalid preferences. Check location, budget, cuisine, and rating.",
    "unexpected_error": "Something went wrong while generating recommendations.",
}


def validate_preferences(
    preferences: UserPreferences | dict[str, Any],
) -> UserPreferences:
    """
    Validate and normalize user preferences (architecture §4.7, §6.1).

    Raises
    ------
    ValidationError
        If required fields, budget enum, or min_rating range are invalid.
    ValueError
        If location or cuisine is empty after stripping.
    """
    if isinstance(preferences, UserPreferences):
        prefs = preferences
    else:
        prefs = UserPreferences.model_validate(preferences)

    if not prefs.location:
        raise ValueError("location must not be empty")
    if not prefs.cuisine:
        raise ValueError("cuisine must not be empty")

    return prefs


def _ensure_restaurants_loaded() -> None:
    """Load the dataset if the in-memory store is empty."""
    load_restaurants()


def _log_stage(
    stage: str,
    elapsed_sec: float,
    *,
    extra: str = "",
) -> None:
    msg = f"Stage {stage} completed in {elapsed_sec * 1000:.1f}ms"
    if extra:
        msg = f"{msg} ({extra})"
    logger.info(msg)


def recommend(
    preferences: UserPreferences | dict[str, Any],
    *,
    skip_load: bool = False,
) -> RecommendResponse:
    """
    Run the full recommendation pipeline.

    Sequence: validate → load data → filter → [no results | LLM rank/explain → hydrate]

    Returns
    -------
    RecommendationResult
        Ranked recommendations with explanations.
    NoResultsResponse
        When filtering yields zero candidates (LLM is not called).
    ErrorResponse
        On dataset load failure, validation errors, or unexpected failures.
    """
    pipeline_start = time.perf_counter()

    try:
        t0 = time.perf_counter()
        prefs = validate_preferences(preferences)
        _log_stage("validate", time.perf_counter() - t0)
    except ValidationError as exc:
        logger.warning("Preference validation failed: %s", exc)
        return ErrorResponse(
            message=USER_MESSAGES["validation_error"],
            code="validation_error",
        )
    except ValueError as exc:
        logger.warning("Preference validation failed: %s", exc)
        return ErrorResponse(
            message=USER_MESSAGES["validation_error"],
            code="validation_error",
        )

    try:
        if not skip_load:
            t0 = time.perf_counter()
            _ensure_restaurants_loaded()
            _log_stage("ingestion", time.perf_counter() - t0)
    except DatasetLoadError as exc:
        logger.error("Dataset load failed: %s", exc)
        return ErrorResponse(
            message=USER_MESSAGES["dataset_load_failed"],
            code="dataset_load_failed",
        )
    except RuntimeError as exc:
        logger.error("Restaurant store error: %s", exc)
        return ErrorResponse(
            message=USER_MESSAGES["data_not_ready"],
            code="data_not_ready",
        )

    try:
        t0 = time.perf_counter()
        batch = filter_candidates(prefs)
        stats = batch.filter_stats
        _log_stage(
            "filter",
            time.perf_counter() - t0,
            extra=(
                f"before={stats.total_before} after={stats.total_after} "
                f"capped={len(batch.candidates)}"
            ),
        )

        if not batch.candidates:
            logger.info(
                "No candidates after filter; skipping LLM (location=%s)",
                prefs.location,
            )
            response = build_no_results_response(prefs, stats)
            _log_stage("pipeline", time.perf_counter() - pipeline_start)
            return response

        t0 = time.perf_counter()
        result = generate_recommendations(batch)
        _log_stage(
            "recommendation",
            time.perf_counter() - t0,
            extra=(
                f"returned={len(result.recommendations)} "
                f"degraded={result.meta.degraded}"
            ),
        )

        _log_stage("pipeline", time.perf_counter() - pipeline_start)
        return result

    except DatasetLoadError as exc:
        logger.error("Dataset error during pipeline: %s", exc)
        return ErrorResponse(
            message=USER_MESSAGES["dataset_load_failed"],
            code="dataset_load_failed",
        )
    except Exception as exc:
        logger.exception("Unexpected pipeline error: %s", exc)
        return ErrorResponse(
            message=USER_MESSAGES["unexpected_error"],
            code="unexpected_error",
        )
