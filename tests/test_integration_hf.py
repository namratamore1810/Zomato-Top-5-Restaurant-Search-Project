"""Optional integration tests that download from Hugging Face (slow)."""

from __future__ import annotations

import pytest

from app.ingestion.loader import load_restaurants
from app.ingestion.store import reset_store


@pytest.mark.integration
def test_load_from_huggingface():
  reset_store()
  restaurants = load_restaurants(force_reload=True)
  assert len(restaurants) > 1000
  assert all(r.name and r.location for r in restaurants[:10])
