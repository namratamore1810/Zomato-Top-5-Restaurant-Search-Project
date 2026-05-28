"""Unit tests for LLM client (Groq adapter and mock)."""

from __future__ import annotations

import json

import pytest

from app.llm.client import (
    GroqLLMClient,
    LLMClient,
    LLMClientError,
    MockLLMClient,
    _parse_candidate_ids_from_prompt,
    create_llm_client,
)
from config.settings import clear_settings_cache


SAMPLE_PROMPT = """=== CANDIDATE RESTAURANTS ===
[{"id": "a1", "name": "Cafe A"}, {"id": "b2", "name": "Cafe B"}]
=== INSTRUCTIONS ===
Rank the top 2 restaurants
"""


def test_parse_candidate_ids_from_prompt():
    assert _parse_candidate_ids_from_prompt(SAMPLE_PROMPT) == ["a1", "b2"]


def test_mock_client_returns_valid_json():
    client = MockLLMClient()
    raw = client.complete_json(SAMPLE_PROMPT)
    data = json.loads(raw)
    assert "summary" in data
    assert len(data["recommendations"]) == 2
    assert data["recommendations"][0]["restaurant_id"] == "a1"
    assert data["recommendations"][0]["rank"] == 1


def test_create_llm_client_uses_mock_when_no_groq_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    clear_settings_cache()
    client = create_llm_client()
    assert isinstance(client, MockLLMClient)


def test_create_llm_client_explicit_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    clear_settings_cache()
    client = create_llm_client()
    assert isinstance(client, MockLLMClient)


def test_create_llm_client_groq_when_key_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    clear_settings_cache()
    client = create_llm_client()
    assert isinstance(client, GroqLLMClient)


def test_create_llm_client_unsupported_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    clear_settings_cache()
    with pytest.raises(LLMClientError, match="Unsupported"):
        create_llm_client()


def test_llm_client_facade_delegates_to_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    clear_settings_cache()
    client = LLMClient()
    raw = client.complete_json(SAMPLE_PROMPT)
    data = json.loads(raw)
    assert data["recommendations"][0]["restaurant_id"] == "a1"
