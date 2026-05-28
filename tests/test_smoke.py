"""Smoke tests for project imports."""

from app import __version__
from app.models import BudgetTier, Restaurant, UserPreferences
from app.orchestrator import recommend, validate_preferences
from config.settings import get_settings


def test_version():
  assert __version__ == "0.1.0"


def test_settings_defaults():
  settings = get_settings()
  assert "zomato" in settings.hf_dataset_id.lower()
  assert settings.llm_provider == "groq"
  assert settings.llm_model == "llama-3.3-70b-versatile"


def test_restaurant_model():
  restaurant = Restaurant(
    id="abc123",
    name="Test Cafe",
    location="bangalore",
    cuisines=["Italian"],
    rating=4.5,
    cost=500.0,
    budget_tier=BudgetTier.MEDIUM,
  )
  assert restaurant.name == "Test Cafe"


def test_user_preferences_model():
  prefs = UserPreferences(
    location="Delhi",
    budget="medium",
    cuisine="Italian",
    min_rating=4.0,
  )
  assert prefs.location == "Delhi"


def test_orchestrator_import():
  assert callable(recommend)
  assert callable(validate_preferences)
