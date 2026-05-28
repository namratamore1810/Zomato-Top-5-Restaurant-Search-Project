"""
Filter & prep service — Integration Layer (Phase 2).

Pipeline order (architecture §4.3):
  1. Location match (normalized, case-insensitive substring)
  2. Cuisine match (tag overlap / substring; OR across comma-separated inputs)
  3. Minimum rating (inclusive)
  4. Budget tier match
  5. Sort by rating desc, then name, then id
  6. Cap at MAX_CANDIDATES

If strict filtering yields zero rows and FALLBACK_RELAXATION is enabled:
  - Retry relaxing cuisine only, then budget only (never both at once).
"""

from __future__ import annotations

import json
import logging
import re

from app.ingestion.normalize import LOCATION_SYNONYMS
from app.ingestion.store import get_all_restaurants
from app.models import (
  BudgetPreference,
  CandidateBatch,
  FilterStats,
  NoResultsResponse,
  Restaurant,
  UserPreferences,
)
from config.settings import settings

logger = logging.getLogger(__name__)

RATING_EPSILON = 1e-6


def _normalize_location_str(location: str) -> str:
  lowered = location.strip().lower()
  return LOCATION_SYNONYMS.get(lowered, lowered)


def _normalize_cuisine_str(cuisine: str) -> str:
  return cuisine.strip().lower().replace("-", " ")


def _parse_user_cuisines(cuisine: str) -> list[str]:
  """Support single or comma-separated cuisines (OR match)."""
  parts = re.split(r"[,|/]", cuisine)
  normalized = [_normalize_cuisine_str(part) for part in parts if part.strip()]
  return normalized or [_normalize_cuisine_str(cuisine)]


def _match_location(restaurant: Restaurant, user_location: str) -> bool:
  user_norm = _normalize_location_str(user_location)
  restaurant_loc = restaurant.location.lower()
  if user_norm in restaurant_loc or restaurant_loc in user_norm:
    return True

  # Also allow matching against the broader listed city (kept in metadata),
  # so users can search by city (e.g. "Bangalore") even when Restaurant.location
  # is a locality/area (e.g. "indiranagar").
  listed_city = restaurant.metadata.get("listed_city")
  if isinstance(listed_city, str) and listed_city.strip():
    city_norm = _normalize_location_str(listed_city)
    return user_norm in city_norm or city_norm in user_norm

  return False


def _match_cuisine(restaurant: Restaurant, user_cuisines: list[str]) -> bool:
  if not restaurant.cuisines:
    return False
  restaurant_cuisines = [_normalize_cuisine_str(c) for c in restaurant.cuisines]
  return any(
    user_c in rest_c or rest_c in user_c
    for user_c in user_cuisines
    for rest_c in restaurant_cuisines
  )


def _match_rating(restaurant: Restaurant, min_rating: float) -> bool:
  return restaurant.rating >= min_rating - RATING_EPSILON


def _match_budget(restaurant: Restaurant, budget: BudgetPreference) -> bool:
  return restaurant.budget_tier.value == budget.value


def _apply_filters(
  restaurants: list[Restaurant],
  preferences: UserPreferences,
  *,
  relax_cuisine: bool = False,
  relax_budget: bool = False,
) -> list[Restaurant]:
  user_cuisines = _parse_user_cuisines(preferences.cuisine)
  filtered: list[Restaurant] = []

  for restaurant in restaurants:
    if not _match_location(restaurant, preferences.location):
      continue
    if not relax_cuisine and not _match_cuisine(restaurant, user_cuisines):
      continue
    if not _match_rating(restaurant, preferences.min_rating):
      continue
    if not relax_budget and not _match_budget(restaurant, preferences.budget):
      continue
    filtered.append(restaurant)

  return filtered


def _sort_candidates(candidates: list[Restaurant]) -> list[Restaurant]:
  return sorted(candidates, key=lambda r: (-r.rating, r.name.lower(), r.id))


def serialize_candidates(candidates: list[Restaurant]) -> str:
  """Compact JSON for LLM prompt (Phase 3)."""
  payload = [
    {
      "id": r.id,
      "name": r.name,
      "location": r.location,
      "cuisines": r.cuisines,
      "rating": r.rating,
      "cost": r.cost,
      "budget_tier": r.budget_tier.value,
    }
    for r in candidates
  ]
  return json.dumps(payload, ensure_ascii=False)


def build_no_results_response(
  preferences: UserPreferences,
  filter_stats: FilterStats,
) -> NoResultsResponse:
  suggestions = [
    "Try lowering your minimum rating",
    "Try a different cuisine or location",
  ]
  if filter_stats.relaxed:
    suggestions.append("Filters were partially relaxed but still found no matches")

  return NoResultsResponse(
    message=(
      f"No restaurants match your preferences in "
      f"{preferences.location.strip()}."
    ),
    suggestions=suggestions,
    filter_stats=filter_stats,
  )


def filter_candidates(preferences: UserPreferences) -> CandidateBatch:
  """
  Filter restaurants from the in-memory store into a bounded CandidateBatch.

  The LLM must only receive ``batch.candidates`` (never the full dataset).
  """
  try:
    all_restaurants = get_all_restaurants()
  except RuntimeError as exc:
    raise RuntimeError(
      "Restaurant data not loaded. Call load_restaurants() first."
    ) from exc

  total_before = len(all_restaurants)
  candidates = _apply_filters(all_restaurants, preferences)
  relaxed = False
  relaxed_rules: list[str] = []

  if not candidates and settings.fallback_relaxation:
    candidates = _apply_filters(
      all_restaurants,
      preferences,
      relax_cuisine=True,
      relax_budget=False,
    )
    if candidates:
      relaxed = True
      relaxed_rules = ["cuisine"]
      logger.info("Relaxed cuisine filter for %s", preferences.location)
    else:
      candidates = _apply_filters(
        all_restaurants,
        preferences,
        relax_cuisine=False,
        relax_budget=True,
      )
      if candidates:
        relaxed = True
        relaxed_rules = ["budget"]
        logger.info("Relaxed budget filter for %s", preferences.location)

  candidates = _sort_candidates(candidates)
  total_after = len(candidates)
  capped = candidates[: settings.max_candidates]

  filter_stats = FilterStats(
    total_before=total_before,
    total_after=total_after,
    relaxed=relaxed,
    relaxed_rules=relaxed_rules,
  )

  return CandidateBatch(
    preferences=preferences,
    candidates=capped,
    filter_stats=filter_stats,
    serialized_for_prompt=serialize_candidates(capped),
  )


# Architecture §6.1 alias
filter = filter_candidates
