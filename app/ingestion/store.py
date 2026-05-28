"""In-memory singleton store for normalized restaurants."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from app.models import Restaurant

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_restaurants: list[Restaurant] | None = None
_ingestion_stats: dict[str, int] | None = None


class RestaurantStore:
  """Thread-safe in-memory restaurant store."""

  def __init__(self) -> None:
    self._restaurants: list[Restaurant] = []
    self._stats: dict[str, int] = {}

  def set_restaurants(
    self,
    restaurants: list[Restaurant],
    stats: dict[str, int] | None = None,
  ) -> None:
    self._restaurants = restaurants
    self._stats = stats or {}
    logger.info("Restaurant store updated: %d restaurants", len(restaurants))

  @property
  def restaurants(self) -> list[Restaurant]:
    return self._restaurants

  @property
  def stats(self) -> dict[str, int]:
    return self._stats

  def __len__(self) -> int:
    return len(self._restaurants)


def get_restaurant_store() -> RestaurantStore:
  global _restaurants, _ingestion_stats
  with _lock:
    if _restaurants is None:
      return RestaurantStore()
    store = RestaurantStore()
    store.set_restaurants(_restaurants, _ingestion_stats)
    return store


def set_global_restaurants(
  restaurants: list[Restaurant],
  stats: dict[str, int] | None = None,
) -> None:
  global _restaurants, _ingestion_stats
  with _lock:
    _restaurants = restaurants
    _ingestion_stats = stats


def get_all_restaurants() -> list[Restaurant]:
  global _restaurants
  with _lock:
    if _restaurants is None:
      raise RuntimeError(
        "Restaurant data not loaded. Call load_restaurants() first."
      )
    return list(_restaurants)


def reset_store() -> None:
  """Clear cached restaurants (for tests)."""
  global _restaurants, _ingestion_stats
  with _lock:
    _restaurants = None
    _ingestion_stats = None
