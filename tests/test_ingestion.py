"""Unit tests for data ingestion and normalization (Phase 1)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.ingestion.loader import DatasetLoadError, ingest_dataframe, load_restaurants
from app.ingestion.normalize import (
  assign_budget_tier,
  compute_budget_thresholds,
  normalize_dataframe,
  normalize_records,
  parse_cost,
  parse_cuisines,
  parse_rating,
)
from app.ingestion.store import get_all_restaurants, reset_store
from app.models import BudgetTier


class TestParsers:
  def test_parse_rating_valid(self):
    assert parse_rating("4.1/5") == 4.1
    assert parse_rating("4.5") == 4.5

  def test_parse_rating_invalid(self):
    assert parse_rating("NEW") is None
    assert parse_rating("-") is None
    assert parse_rating("") is None

  def test_parse_cost(self):
    assert parse_cost("800") == 800.0
    assert parse_cost("1,000") == 1000.0
    assert parse_cost("300, 500") == 400.0

  def test_parse_cuisines(self):
    assert parse_cuisines("North Indian, Chinese") == ["North Indian", "Chinese"]
    assert parse_cuisines("") == []


class TestBudgetTiers:
  def test_compute_thresholds_small_sample(self):
    low_max, medium_max = compute_budget_thresholds([100, 200, 500, 1000, 2500])
    assert low_max <= medium_max

  def test_assign_budget_tier(self):
    assert assign_budget_tier(100, 300, 700) == BudgetTier.LOW
    assert assign_budget_tier(500, 300, 700) == BudgetTier.MEDIUM
    assert assign_budget_tier(900, 300, 700) == BudgetTier.HIGH
    assert assign_budget_tier(None, 300, 700) == BudgetTier.MEDIUM


class TestNormalization:
  def test_normalize_drops_invalid_rows(self, sample_dataframe: pd.DataFrame):
    restaurants, stats = normalize_dataframe(sample_dataframe)

    assert stats["dropped_missing_name"] >= 1
    assert stats["dropped_invalid_rating"] >= 1
    assert stats["dropped_missing_location"] >= 1
    assert stats["output_rows"] == len(restaurants)
    assert stats["output_rows"] < stats["input_rows"]

  def test_restaurant_has_required_fields(self, sample_dataframe: pd.DataFrame):
    restaurants, _ = normalize_dataframe(sample_dataframe)

    for restaurant in restaurants:
      assert restaurant.id
      assert restaurant.name
      assert restaurant.location
      assert isinstance(restaurant.cuisines, list)
      assert 0.0 <= restaurant.rating <= 5.0
      assert restaurant.budget_tier in BudgetTier

  def test_location_normalized(self, sample_dataframe: pd.DataFrame):
    restaurants, _ = normalize_dataframe(sample_dataframe)
    locations = {r.location for r in restaurants}
    assert "bangalore" in locations
    assert "delhi" in locations

  def test_stable_ids_from_url(self, sample_dataframe: pd.DataFrame):
    restaurants, _ = normalize_dataframe(sample_dataframe)
    ids = [r.id for r in restaurants]
    assert len(ids) == len(set(ids))

  def test_empty_records(self):
    restaurants, stats = normalize_records([])
    assert restaurants == []
    assert stats["output_rows"] == 0


class TestLoaderAndStore:
  def test_load_restaurants_from_fixture(self, sample_dataframe: pd.DataFrame):
    restaurants = load_restaurants(raw_df=sample_dataframe, force_reload=True)

    assert len(restaurants) >= 4
    assert len(get_all_restaurants()) == len(restaurants)

  def test_store_persists_without_reload(self, sample_dataframe: pd.DataFrame):
    first = load_restaurants(raw_df=sample_dataframe, force_reload=True)
    second = load_restaurants()
    assert first is not second
    assert len(first) == len(second)

  def test_ingest_empty_dataframe_raises(self):
    with pytest.raises(DatasetLoadError):
      ingest_dataframe(pd.DataFrame())

  def test_get_all_before_load_raises(self):
    reset_store()
    with pytest.raises(RuntimeError, match="not loaded"):
      get_all_restaurants()
