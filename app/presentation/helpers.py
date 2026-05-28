"""Pure helpers for the presentation layer (testable without Streamlit)."""

from __future__ import annotations

from app.models import (
    BudgetPreference,
    ErrorResponse,
    NoResultsResponse,
    RecommendationMeta,
    RecommendationResult,
    UserPreferences,
)
from config.settings import settings

DEGRADED_MESSAGES: dict[str, str] = {
    "llm_api_error": (
        "AI ranking is temporarily unavailable. "
        "Showing top-rated matches from your filters."
    ),
    "llm_parsing_failed": (
        "Could not parse AI rankings. Showing top-rated matches from your filters."
    ),
    "partial_llm_response": (
        "AI returned fewer picks than requested. Remaining slots use filter ranking."
    ),
    "unexpected_error": (
        "An unexpected issue occurred. Showing top-rated matches from your filters."
    ),
    "zero_candidates": "No restaurants matched your filters.",
}


def build_preferences_from_form(
    *,
    location: str,
    budget: str,
    cuisine: str,
    min_rating: float,
    additional_preferences: str | None = None,
    top_n: int | None = None,
) -> UserPreferences:
    """Build validated preferences from form field values."""
    extras = (additional_preferences or "").strip() or None
    return UserPreferences(
        location=location.strip(),
        budget=BudgetPreference(budget),
        cuisine=cuisine.strip(),
        min_rating=min_rating,
        additional_preferences=extras,
        top_n=top_n if top_n is not None else settings.default_top_n,
    )


def should_show_summary(summary: str | None) -> bool:
    """EC-V05: hide summary section when absent."""
    return bool(summary and summary.strip())


def should_show_meta(
    response: RecommendationResult | NoResultsResponse | ErrorResponse,
) -> bool:
    """EC-V06: do not show confusing '0 considered' on no-results."""
    if not isinstance(response, RecommendationResult):
        return False
    return response.meta.candidates_considered > 0


def degraded_message(meta: RecommendationMeta) -> str | None:
    """User-facing degraded-mode copy (EC-V08)."""
    if not meta.degraded:
        return None
    reason = meta.degraded_reason or "unknown"
    return DEGRADED_MESSAGES.get(
        reason,
        "Results may use filter ranking instead of full AI personalization.",
    )


def no_results_title(response: NoResultsResponse) -> str:
    """Headline for empty filter results."""
    return response.message


def no_results_suggestions(response: NoResultsResponse) -> list[str]:
    return list(response.suggestions)
