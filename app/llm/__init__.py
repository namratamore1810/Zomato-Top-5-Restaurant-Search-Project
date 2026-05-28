"""LLM Recommendation Engine module."""

from __future__ import annotations

from app.llm.client import LLMClient, LLMClientError, create_llm_client
from app.llm.engine import generate_recommendations
from app.llm.parser import hydrate_recommendations, parse_llm_response
from app.llm.prompt_builder import build_prompt

__all__ = [
    "build_prompt",
    "LLMClient",
    "LLMClientError",
    "create_llm_client",
    "parse_llm_response",
    "hydrate_recommendations",
    "generate_recommendations",
]
