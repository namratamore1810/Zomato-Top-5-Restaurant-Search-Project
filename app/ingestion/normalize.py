"""Map raw Hugging Face rows to canonical Restaurant records."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import pandas as pd

from app.models import BudgetTier, Restaurant

logger = logging.getLogger(__name__)

# Raw column names from ManikaSaini/zomato-restaurant-recommendation
COL_URL = "url"
COL_NAME = "name"
COL_ADDRESS = "address"
COL_RATE = "rate"
COL_VOTES = "votes"
COL_LOCATION = "location"
COL_CUISINES = "cuisines"
COL_COST = "approx_cost(for two people)"
COL_LISTED_CITY = "listed_in(city)"
COL_REST_TYPE = "rest_type"
COL_ONLINE_ORDER = "online_order"
COL_BOOK_TABLE = "book_table"

LOCATION_SYNONYMS = {
  "bengaluru": "bangalore",
  "bangalore": "bangalore",
  "new delhi": "delhi",
  "delhi ncr": "delhi",
}

INVALID_RATINGS = frozenset({"", "-", "nan", "none", "new", "null"})


def _is_missing(value: Any) -> bool:
  if value is None:
    return True
  if isinstance(value, float) and pd.isna(value):
    return True
  if isinstance(value, str) and value.strip().lower() in INVALID_RATINGS:
    return True
  return False


def parse_rating(raw: Any) -> float | None:
  """Parse Zomato rate field (e.g. '4.1/5', '4.5', NEW, -)."""
  if _is_missing(raw):
    return None

  text = str(raw).strip().lower()
  if text in INVALID_RATINGS:
    return None

  match = re.search(r"(\d+(?:\.\d+)?)", text)
  if not match:
    return None

  rating = float(match.group(1))
  if rating > 5.0:
    rating = rating / 10.0 if rating <= 50 else 5.0
  if rating < 0.0 or rating > 5.0:
    return None
  return round(rating, 2)


def parse_cost(raw: Any) -> float | None:
  """Parse approximate cost for two (may include currency symbols or ranges)."""
  if _is_missing(raw):
    return None

  text = str(raw).strip().lower()
  if text in INVALID_RATINGS:
    return None

  numbers = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
  if not numbers:
    return None

  values = [float(n) for n in numbers]
  return round(sum(values) / len(values), 2)


def parse_cuisines(raw: Any) -> list[str]:
  if _is_missing(raw):
    return []

  parts = re.split(r"[,|/]", str(raw))
  cuisines: list[str] = []
  seen: set[str] = set()
  for part in parts:
    cleaned = part.strip()
    if not cleaned:
      continue
    key = cleaned.lower()
    if key not in seen:
      seen.add(key)
      cuisines.append(cleaned)
  return cuisines


def normalize_location(city: str | None, locality: str | None) -> str | None:
  """
  Normalize a user-facing location string.

  We prefer the dataset's locality/area (e.g. Indiranagar, Bellandur) so the UI
  can offer these granular options. The listed city is still kept in metadata
  (`listed_city`) for broader matching (e.g. user selects/enters "Bangalore").
  """
  for candidate in (locality, city):
    if candidate is None or _is_missing(candidate):
      continue
    text = str(candidate).strip()
    if not text:
      continue
    lowered = text.lower()
    return LOCATION_SYNONYMS.get(lowered, lowered)
  return None


def make_restaurant_id(url: str | None, name: str, index: int) -> str:
  if url and not _is_missing(url):
    return hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:16]
  digest = hashlib.sha256(f"{name}:{index}".encode("utf-8")).hexdigest()
  return digest[:16]


def compute_budget_thresholds(costs: list[float]) -> tuple[float, float]:
  """Return (low_max, medium_max) percentile boundaries for tier assignment."""
  if not costs:
    return 300.0, 700.0

  if len(costs) < 10:
    sorted_costs = sorted(costs)
    n = len(sorted_costs)
    low_idx = max(0, n // 3 - 1)
    high_idx = min(n - 1, (2 * n) // 3)
    return sorted_costs[low_idx], sorted_costs[high_idx]

  series = pd.Series(costs)
  low_max = float(series.quantile(0.33))
  medium_max = float(series.quantile(0.66))
  if low_max >= medium_max:
    medium_max = low_max + 1.0
  return low_max, medium_max


def assign_budget_tier(
  cost: float | None,
  low_max: float,
  medium_max: float,
) -> BudgetTier:
  if cost is None:
    return BudgetTier.MEDIUM
  if cost <= low_max:
    return BudgetTier.LOW
  if cost <= medium_max:
    return BudgetTier.MEDIUM
  return BudgetTier.HIGH


def normalize_dataframe(df: pd.DataFrame) -> tuple[list[Restaurant], dict[str, int]]:
  """
  Convert raw dataset rows into Restaurant models.

  Returns restaurants and ingestion stats (dropped_rows, etc.).
  """
  stats = {
    "input_rows": len(df),
    "dropped_missing_name": 0,
    "dropped_missing_location": 0,
    "dropped_invalid_rating": 0,
    "output_rows": 0,
  }

  parsed_rows: list[dict[str, Any]] = []

  for index, row in df.iterrows():
    name_raw = row.get(COL_NAME)
    if _is_missing(name_raw):
      stats["dropped_missing_name"] += 1
      continue

    city_raw = row.get(COL_LISTED_CITY)
    locality_raw = row.get(COL_LOCATION)
    location = normalize_location(
      str(city_raw) if not _is_missing(city_raw) else None,
      str(locality_raw) if not _is_missing(locality_raw) else None,
    )
    if location is None:
      stats["dropped_missing_location"] += 1
      continue

    rating = parse_rating(row.get(COL_RATE))
    if rating is None:
      stats["dropped_invalid_rating"] += 1
      continue

    cost = parse_cost(row.get(COL_COST))
    cuisines = parse_cuisines(row.get(COL_CUISINES))
    name = str(name_raw).strip()
    url = row.get(COL_URL)

    parsed_rows.append(
      {
        "id": make_restaurant_id(
          str(url) if not _is_missing(url) else None,
          name,
          int(index) if isinstance(index, int) else len(parsed_rows),
        ),
        "name": name,
        "location": location,
        "cuisines": cuisines,
        "rating": rating,
        "cost": cost,
        "metadata": {
          "address": None if _is_missing(row.get(COL_ADDRESS)) else str(row.get(COL_ADDRESS)).strip(),
          "locality": None if _is_missing(locality_raw) else str(locality_raw).strip(),
          "listed_city": None if _is_missing(city_raw) else str(city_raw).strip(),
          "rest_type": None if _is_missing(row.get(COL_REST_TYPE)) else str(row.get(COL_REST_TYPE)).strip(),
          "votes": int(row[COL_VOTES]) if COL_VOTES in row and not pd.isna(row.get(COL_VOTES)) else None,
          "online_order": None if _is_missing(row.get(COL_ONLINE_ORDER)) else str(row.get(COL_ONLINE_ORDER)).strip(),
          "book_table": None if _is_missing(row.get(COL_BOOK_TABLE)) else str(row.get(COL_BOOK_TABLE)).strip(),
        },
      }
    )

  costs = [row["cost"] for row in parsed_rows if row["cost"] is not None]
  low_max, medium_max = compute_budget_thresholds(costs)
  logger.info(
    "Budget thresholds: low <= %.2f, medium <= %.2f, high > %.2f",
    low_max,
    medium_max,
    medium_max,
  )

  restaurants: list[Restaurant] = []
  for row in parsed_rows:
    tier = assign_budget_tier(row["cost"], low_max, medium_max)
    restaurants.append(
      Restaurant(
        id=row["id"],
        name=row["name"],
        location=row["location"],
        cuisines=row["cuisines"],
        rating=row["rating"],
        cost=row["cost"],
        budget_tier=tier,
        metadata=row["metadata"],
      )
    )

  stats["output_rows"] = len(restaurants)
  return restaurants, stats


def normalize_records(records: list[dict[str, Any]]) -> tuple[list[Restaurant], dict[str, int]]:
  """Normalize a list of dict records (used in tests)."""
  if not records:
    return [], {"input_rows": 0, "output_rows": 0}
  return normalize_dataframe(pd.DataFrame(records))
