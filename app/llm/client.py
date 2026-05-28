"""LLM client: Groq adapter (Phase 3) and mock for CI / local runs without API key."""

from __future__ import annotations

import json
import logging
import re
from typing import Protocol

from config.settings import settings

logger = logging.getLogger(__name__)

_CANDIDATES_MARKER = "=== CANDIDATE RESTAURANTS ==="
_INSTRUCTIONS_MARKER = "=== INSTRUCTIONS ==="


class LLMClientError(RuntimeError):
    """Raised when the LLM client call fails."""


class LLMClientProtocol(Protocol):
    def complete(self, prompt: str) -> str: ...

    def complete_json(self, prompt: str) -> str: ...


def _parse_candidate_ids_from_prompt(prompt: str) -> list[str]:
    """Extract restaurant ids from the serialized candidate JSON in the prompt."""
    if _CANDIDATES_MARKER not in prompt:
        return []
    rest = prompt.split(_CANDIDATES_MARKER, 1)[1].strip()
    if _INSTRUCTIONS_MARKER in rest:
        rest = rest.split(_INSTRUCTIONS_MARKER, 1)[0].strip()
    try:
        data = json.loads(rest)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rid = item.get("id") or item.get("restaurant_id")
        if rid is not None:
            ids.append(str(rid).strip())
    return ids


def _parse_top_n_from_prompt(prompt: str, default: int) -> int:
    match = re.search(r"Rank the top (\d+) restaurants", prompt)
    if match:
        return int(match.group(1))
    return default


class MockLLMClient:
    """Deterministic JSON responses for CI and runs without GROQ_API_KEY."""

    def complete(self, prompt: str) -> str:
        return self.complete_json(prompt)

    def complete_json(self, prompt: str) -> str:
        ids = _parse_candidate_ids_from_prompt(prompt)
        top_n = _parse_top_n_from_prompt(prompt, settings.default_top_n)
        recommendations = []
        for rank, rid in enumerate(ids[:top_n], start=1):
            recommendations.append(
                {
                    "restaurant_id": rid,
                    "rank": rank,
                    "explanation": (
                        f"Mock pick #{rank}: strong match for your location, "
                        "cuisine, and budget (no Groq API key configured)."
                    ),
                }
            )
        payload = {
            "summary": (
                "Mock LLM summary for local/CI runs. "
                "Set GROQ_API_KEY to use Groq for real rankings."
            ),
            "recommendations": recommendations,
        }
        return json.dumps(payload, ensure_ascii=False)


class GroqLLMClient:
    """Groq Inference API chat completions."""

    def __init__(self) -> None:
        self.model = settings.llm_model
        self.api_key = settings.groq_api_key
        self.temperature = settings.llm_temperature

    def complete(self, prompt: str) -> str:
        return self._call_groq(prompt, json_mode=False)

    def complete_json(self, prompt: str) -> str:
        return self._call_groq(prompt, json_mode=True)

    def _call_groq(self, prompt: str, json_mode: bool = False) -> str:
        if not self.api_key:
            raise LLMClientError(
                "GROQ_API_KEY not set. Use LLM_PROVIDER=mock or set GROQ_API_KEY."
            )

        try:
            from groq import Groq
        except ImportError as exc:
            logger.error("The 'groq' package is not installed.")
            raise LLMClientError(
                "Groq package not installed. Run 'pip install groq'."
            ) from exc

        try:
            client = Groq(api_key=self.api_key)
            kwargs: dict = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content is None or content.strip() == "":
                raise LLMClientError("Received empty completion from Groq API.")
            return content
        except LLMClientError:
            raise
        except Exception as exc:
            logger.error("Groq API completion failed: %s", exc)
            raise LLMClientError(f"Groq API error: {exc}") from exc


def create_llm_client() -> LLMClientProtocol:
    """Select Groq or mock client based on configuration."""
    provider = settings.llm_provider.lower().strip()
    if provider == "mock":
        logger.debug("Using mock LLM client (LLM_PROVIDER=mock)")
        return MockLLMClient()
    if provider == "groq":
        if not settings.groq_api_key:
            logger.info(
                "GROQ_API_KEY unset; using mock LLM client for recommendations"
            )
            return MockLLMClient()
        return GroqLLMClient()
    raise LLMClientError(
        f"Unsupported LLM provider: {provider!r}. "
        "Supported: groq, mock."
    )


class LLMClient:
    """Facade used by the recommendation engine; delegates to Groq or mock."""

    def __init__(self) -> None:
        self._client = create_llm_client()

    def complete(self, prompt: str) -> str:
        return self._client.complete(prompt)

    def complete_json(self, prompt: str) -> str:
        return self._client.complete_json(prompt)
