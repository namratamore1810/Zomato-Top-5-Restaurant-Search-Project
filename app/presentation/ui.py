"""
Streamlit UI for Zomato Top 5 (Phase 5).

Run: streamlit run app/presentation/ui.py
"""

from __future__ import annotations

import html
import logging
import sys
from pathlib import Path

# Streamlit does not add the project root to sys.path by default.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from app.ingestion.loader import DatasetLoadError, load_restaurants
from app.ingestion.store import get_all_restaurants
from app.models import (
    ErrorResponse,
    NoResultsResponse,
    RecommendationItem,
    RecommendationResult,
)
from app.orchestrator import recommend
from app.presentation.helpers import (
    build_preferences_from_form,
    degraded_message,
    no_results_suggestions,
    no_results_title,
    should_show_meta,
    should_show_summary,
)
from config.settings import settings

logger = logging.getLogger(__name__)

PAGE_TITLE = "Zomato Top 5"
PAGE_ICON = "🍽️"
SPINNER_LABEL = "Finding your top picks…"
LOADING_DATA_LABEL = "Loading restaurant dataset (first run may take a few minutes)…"


def _location_options() -> list[str]:
    """
    Build a sorted list of unique locations from the dataset.

    Note: `Restaurant.location` is normalized (lowercase) and usually represents
    an area/locality. City is preserved separately in metadata (`listed_city`).
    """
    try:
        restaurants = get_all_restaurants()
    except RuntimeError:
        return []
    locations = {
        r.location.strip().lower()
        for r in restaurants
        if isinstance(r.location, str) and r.location.strip()
    }
    return sorted(locations)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .rec-card {
            border: 1px solid #e8e8e8;
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
            background: #fafafa;
        }
        .rec-rank {
            font-size: 1.5rem;
            font-weight: 700;
            color: #e23744;
        }
        .rec-name {
            font-size: 1.15rem;
            font-weight: 600;
            margin: 0.25rem 0;
        }
        .rec-meta {
            color: #555;
            font-size: 0.95rem;
        }
        .rec-explanation {
            margin-top: 0.75rem;
            line-height: 1.5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_dataset_loaded() -> bool:
    """Load HF dataset once per session; return False on failure."""
    if st.session_state.get("dataset_ready"):
        return True
    if st.session_state.get("dataset_error"):
        return False

    try:
        with st.spinner(LOADING_DATA_LABEL):
            load_restaurants()
        st.session_state["dataset_ready"] = True
        return True
    except DatasetLoadError as exc:
        logger.error("Dataset load failed in UI: %s", exc)
        st.session_state["dataset_error"] = (
            "Unable to load restaurant data. Please check your connection and try again."
        )
        return False


def render_preference_form() -> bool:
    """
    Render preference inputs. Returns True if the user submitted the form.
    """
    st.subheader("Your preferences")

    # To populate the location dropdown we need the dataset loaded.
    dataset_ready = ensure_dataset_loaded()
    location_choices = _location_options() if dataset_ready else []

    with st.form("preference_form", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            if location_choices:
                location = st.selectbox(
                    "Location",
                    options=location_choices,
                    index=0,
                    format_func=lambda s: str(s).title(),
                    help="Choose an area/locality (type to search). City names still work in filtering.",
                )
            else:
                # Fallback when dataset isn't loaded yet.
                location = st.text_input(
                    "Location",
                    placeholder="e.g. Bangalore, Indiranagar, Bellandur",
                    help="City or area to search in",
                )
            cuisine = st.text_input(
                "Cuisine",
                placeholder="e.g. Italian, Chinese",
                help="Comma-separated for multiple (OR match)",
            )

        with col2:
            budget = st.selectbox(
                "Budget",
                options=["low", "medium", "high"],
                index=1,
                help="Budget tier for two people",
            )
            min_rating = st.slider(
                "Minimum rating",
                min_value=0.0,
                max_value=5.0,
                value=4.0,
                step=0.1,
                help="Inclusive lower bound (0–5)",
            )

        additional = st.text_area(
            "Additional preferences (optional)",
            placeholder="e.g. family-friendly, rooftop seating, quick service",
            help="Free-text vibe passed to the AI for ranking",
        )

        submitted = st.form_submit_button(
            "Get my top picks",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return False

    if not str(location).strip() or not cuisine.strip():
        st.error("Please enter both location and cuisine.")
        return False

    try:
        prefs = build_preferences_from_form(
            location=str(location),
            budget=budget,
            cuisine=cuisine,
            min_rating=min_rating,
            additional_preferences=additional,
        )
    except Exception as exc:
        logger.warning("Form validation failed: %s", exc)
        st.error(
            "Invalid preferences. Check location, budget, cuisine, and rating."
        )
        return False

    st.session_state["last_preferences"] = prefs

    if not dataset_ready:
        st.error(st.session_state.get("dataset_error", "Dataset unavailable."))
        return False

    with st.spinner(SPINNER_LABEL):
        response = recommend(prefs, skip_load=True)

    st.session_state["last_response"] = response
    return True


def render_recommendation_card(item: RecommendationItem) -> None:
    """Render a single recommendation card (architecture RecommendationCard)."""
    safe_name = html.escape(item.name)
    safe_cuisine = html.escape(item.cuisine)
    safe_cost = html.escape(item.estimated_cost)
    safe_explanation = html.escape(item.explanation)

    st.markdown(
        f"""
        <div class="rec-card">
            <div class="rec-rank">#{item.rank}</div>
            <div class="rec-name">{safe_name}</div>
            <div class="rec-meta">
                {safe_cuisine} &nbsp;·&nbsp; ★ {item.rating:.1f}
                &nbsp;·&nbsp; {safe_cost}
            </div>
            <div class="rec-explanation">{safe_explanation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_success_result(result: RecommendationResult) -> None:
    """Display ranked recommendations with summary and meta."""
    degraded = degraded_message(result.meta)
    if degraded:
        st.warning(degraded)

    if should_show_summary(result.summary):
        st.markdown("### Overview")
        st.info(result.summary)

    count = len(result.recommendations)
    if count < result.meta.top_n:
        st.caption(f"Showing {count} recommendation(s) based on available matches.")

    st.markdown("### Your top picks")
    for item in result.recommendations:
        render_recommendation_card(item)

    if should_show_meta(result):
        st.caption(
            f"Considered {result.meta.candidates_considered} matching restaurants "
            f"· showing top {result.meta.top_n}"
        )


def render_no_results(response: NoResultsResponse) -> None:
    """Friendly empty state (no stack trace)."""
    st.warning(no_results_title(response))
    suggestions = no_results_suggestions(response)
    if suggestions:
        st.markdown("**Try:**")
        for tip in suggestions:
            st.markdown(f"- {tip}")


def render_error(response: ErrorResponse) -> None:
    """User-safe error banner."""
    st.error(response.message)


def render_last_response() -> None:
    """Render cached response from session state (EC-V01)."""
    response = st.session_state.get("last_response")
    if response is None:
        return

    if isinstance(response, RecommendationResult):
        render_success_result(response)
    elif isinstance(response, NoResultsResponse):
        render_no_results(response)
    elif isinstance(response, ErrorResponse):
        render_error(response)


def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    st.title("🍽️ Zomato Top 5")
    st.markdown(
        "Get **personalized restaurant recommendations** powered by real Zomato data "
        "and AI — filtered to your location, budget, cuisine, and rating."
    )

    with st.sidebar:
        st.header("About")
        st.markdown(
            f"- Default picks: **{settings.default_top_n}** restaurants\n"
            f"- LLM: **{settings.llm_provider}** (`{settings.llm_model}`)\n"
            "- First launch downloads the Hugging Face dataset"
        )
        if st.session_state.get("dataset_ready"):
            st.success("Restaurant data loaded")
        elif st.session_state.get("dataset_error"):
            st.error("Dataset not loaded")
        else:
            st.caption("Dataset loads on first search")

        if st.button("Reload dataset", key="reload_dataset"):
            st.session_state.pop("dataset_ready", None)
            st.session_state.pop("dataset_error", None)
            if ensure_dataset_loaded():
                st.success("Dataset reloaded")

    render_preference_form()
    render_last_response()


if __name__ == "__main__":
    main()
