"""Shared data contracts for the recommendation pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BudgetTier(str, Enum):
  LOW = "low"
  MEDIUM = "medium"
  HIGH = "high"


class BudgetPreference(str, Enum):
  LOW = "low"
  MEDIUM = "medium"
  HIGH = "high"


class Restaurant(BaseModel):
  """Canonical restaurant record after ingestion and normalization."""

  id: str
  name: str
  location: str
  cuisines: list[str] = Field(default_factory=list)
  rating: float = Field(ge=0.0, le=5.0)
  cost: float | None = None
  budget_tier: BudgetTier
  metadata: dict[str, Any] = Field(default_factory=dict)


class UserPreferences(BaseModel):
  """User inputs collected from CLI or UI (Phase 2+)."""

  location: str
  budget: BudgetPreference
  cuisine: str
  min_rating: float = Field(ge=0.0, le=5.0)
  additional_preferences: str | None = None
  top_n: int = Field(default=5, ge=1, le=50)

  @field_validator("location", "cuisine")
  @classmethod
  def strip_required_strings(cls, value: str) -> str:
    return value.strip()


class FilterStats(BaseModel):
  total_before: int = 0
  total_after: int = 0
  relaxed: bool = False
  relaxed_rules: list[str] = Field(default_factory=list)


class CandidateBatch(BaseModel):
  preferences: UserPreferences
  candidates: list[Restaurant] = Field(default_factory=list)
  filter_stats: FilterStats = Field(default_factory=FilterStats)
  serialized_for_prompt: str = ""


class RecommendationItem(BaseModel):
  rank: int
  restaurant_id: str
  name: str
  cuisine: str
  rating: float
  estimated_cost: str
  explanation: str
  budget_tier: str | None = None


class RecommendationMeta(BaseModel):
  candidates_considered: int = 0
  top_n: int = 5
  degraded: bool = False
  degraded_reason: str | None = None


class RecommendationResult(BaseModel):
  status: str = "success"
  summary: str | None = None
  preferences: UserPreferences
  recommendations: list[RecommendationItem] = Field(default_factory=list)
  meta: RecommendationMeta = Field(default_factory=RecommendationMeta)


class NoResultsResponse(BaseModel):
  status: str = "no_results"
  message: str
  suggestions: list[str] = Field(default_factory=list)
  filter_stats: FilterStats = Field(default_factory=FilterStats)


class ErrorResponse(BaseModel):
  status: str = "error"
  message: str
  code: str
