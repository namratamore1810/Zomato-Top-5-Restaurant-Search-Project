"""Prompt builder for recommendation engine."""

from __future__ import annotations

import os
from pathlib import Path

from app.models import CandidateBatch

# Template path relative to app/llm/prompt_builder.py
PROMPT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "v1_rank_and_explain.txt"
)


def build_prompt(batch: CandidateBatch) -> str:
    """
    Load the prompt template and inject preferences, candidates, and top_n.
    """
    if not os.path.exists(PROMPT_TEMPLATE_PATH):
        raise FileNotFoundError(
            f"Prompt template file not found at: {PROMPT_TEMPLATE_PATH}"
        )

    with open(PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    prefs = batch.preferences
    additional_prefs = prefs.additional_preferences or "None"

    # In case additional preferences is extremely long, sanitize or let it pass.
    # We strip/trim it slightly here to prevent format issues.
    additional_prefs = additional_prefs.strip()

    prompt_text = template.format(
        location=prefs.location,
        cuisine=prefs.cuisine,
        budget=prefs.budget.value,
        min_rating=prefs.min_rating,
        additional_preferences=additional_prefs,
        candidates_json=batch.serialized_for_prompt,
        top_n=prefs.top_n,
    )

    return prompt_text
