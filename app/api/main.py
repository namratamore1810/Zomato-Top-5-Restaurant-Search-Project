from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion.loader import load_restaurants
from app.ingestion.store import get_all_restaurants
from app.models import (
    ErrorResponse,
    NoResultsResponse,
    RecommendationResult,
    UserPreferences,
)
from app.orchestrator import recommend

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TasteTrail AI API",
    description="Backend API for Zomato Top 5 restaurant recommendation engine.",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Load dataset on startup."""
    logger.info("Initializing dataset on startup...")
    try:
        load_restaurants()
        logger.info("Dataset successfully loaded.")
    except Exception as exc:
        logger.error("Failed to load dataset on startup: %s", exc)


@app.get("/api/locations", response_model=list[str])
def get_locations():
    """Retrieve unique normalized locations from the dataset."""
    try:
        restaurants = get_all_restaurants()
        locations = {
            r.location.strip().lower()
            for r in restaurants
            if isinstance(r.location, str) and r.location.strip()
        }
        return sorted(locations)
    except Exception as exc:
        logger.error("Error retrieving locations: %s", exc)
        raise HTTPException(status_code=500, detail="Error retrieving locations")


@app.get("/api/cuisines", response_model=list[str])
def get_cuisines():
    """Retrieve unique cuisines from the dataset."""
    try:
        restaurants = get_all_restaurants()
        cuisines = set()
        for r in restaurants:
            for c in r.cuisines:
                c_stripped = c.strip()
                if c_stripped:
                    cuisines.add(c_stripped)
        return sorted(cuisines)
    except Exception as exc:
        logger.error("Error retrieving cuisines: %s", exc)
        raise HTTPException(status_code=500, detail="Error retrieving cuisines")


@app.post("/api/recommend")
def get_recommendations(preferences: UserPreferences):
    """
    Run the full recommendation pipeline for the given preferences.
    Returns RecommendationResult, NoResultsResponse, or ErrorResponse.
    """
    logger.info("Received recommendation request: %s", preferences)
    try:
        response = recommend(preferences, skip_load=True)
        return response
    except Exception as exc:
        logger.exception("Unexpected error in API endpoint: %s", exc)
        return ErrorResponse(
            status="error",
            message="Internal server error occurred.",
            code="internal_error",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000, reload=True)
