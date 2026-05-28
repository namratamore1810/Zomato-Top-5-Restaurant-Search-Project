"""Load Zomato dataset from Hugging Face and populate the in-memory store."""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd
from datasets import load_dataset

from app.ingestion.normalize import normalize_dataframe
from app.ingestion.store import get_all_restaurants, set_global_restaurants
from app.models import Restaurant
from config.settings import settings

logger = logging.getLogger(__name__)


class DatasetLoadError(RuntimeError):
  """Raised when the Hugging Face dataset cannot be loaded."""


def _raw_rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
  return pd.DataFrame(rows)


def fetch_raw_dataframe(dataset_id: str | None = None) -> pd.DataFrame:
  """Download dataset from Hugging Face and return as DataFrame."""
  dataset_name = dataset_id or settings.hf_dataset_id
  last_error: Exception | None = None

  for attempt in range(1, settings.hf_load_retries + 1):
    try:
      logger.info(
        "Loading dataset '%s' (attempt %d/%d)",
        dataset_name,
        attempt,
        settings.hf_load_retries,
      )
      dataset = load_dataset(dataset_name, split="train")
      df = dataset.to_pandas()
      if df.empty:
        raise DatasetLoadError(f"Dataset '{dataset_name}' is empty.")
      logger.info("Fetched %d raw rows from Hugging Face", len(df))
      return df
    except Exception as exc:
      last_error = exc
      logger.warning("Dataset load attempt %d failed: %s", attempt, exc)
      if attempt < settings.hf_load_retries:
        delay = settings.hf_load_retry_delay_sec * attempt
        time.sleep(delay)

  raise DatasetLoadError(
    f"Unable to load dataset '{dataset_name}' after "
    f"{settings.hf_load_retries} attempts: {last_error}"
  ) from last_error


def ingest_dataframe(df: pd.DataFrame) -> tuple[list[Restaurant], dict[str, int]]:
  """Normalize a DataFrame and return restaurants with stats."""
  restaurants, stats = normalize_dataframe(df)
  if not restaurants:
    raise DatasetLoadError(
      "No valid restaurants after preprocessing. Check dataset schema or filters."
    )
  return restaurants, stats


def load_restaurants(
  *,
  force_reload: bool = False,
  dataset_id: str | None = None,
  raw_df: pd.DataFrame | None = None,
) -> list[Restaurant]:
  """
  Load restaurants into the global in-memory store.

  Parameters
  ----------
  force_reload:
    If True, reload even when cache is populated.
  dataset_id:
    Override Hugging Face dataset id (defaults to settings).
  raw_df:
    Optional pre-loaded DataFrame (used in tests to skip HF download).
  """
  if not force_reload:
    try:
      return get_all_restaurants()
    except RuntimeError:
      pass

  if raw_df is not None:
    df = raw_df
  else:
    df = fetch_raw_dataframe(dataset_id)

  restaurants, stats = ingest_dataframe(df)
  set_global_restaurants(restaurants, stats)

  logger.info(
    "Loaded %d restaurants from Hugging Face (dropped %d rows)",
    stats["output_rows"],
    stats["input_rows"] - stats["output_rows"],
  )
  return restaurants
