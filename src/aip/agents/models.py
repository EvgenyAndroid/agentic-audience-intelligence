"""Replaceable reasoning-model interface. No vendor SDK is required to run or test the platform."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class ReasoningModel(Protocol):
    provider: str
    model_id: str

    def propose(self, role: str, context: Mapping[str, Any]) -> dict[str, Any]:
        """Return {"proposed_verdict", "proposed_reasons", "proposed_next_actions"} from sanitized context only."""
        ...


class NullReasoningModel:
    provider, model_id = "none", "unconfigured"

    def propose(self, role: str, context: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "proposed_verdict": "PROVISIONAL",
            "proposed_reasons": [{"code": "insufficient_information", "detail": "No reasoning model configured"}],
            "proposed_next_actions": ["Configure a reasoning model"],
        }


class ScriptedReasoningModel:
    """Deterministic stand-in for tests and dry runs."""

    provider, model_id = "scripted", "scripted"

    def __init__(self, responses: Sequence[dict[str, Any]]):
        self._responses = list(responses)

    def propose(self, role: str, context: Mapping[str, Any]) -> dict[str, Any]:
        if not self._responses:
            raise RuntimeError("scripted model has no responses left")
        return self._responses.pop(0)


class AnthropicReasoningModel:
    """Optional adapter (pip install .[llm]). Not exercised by the test suite; model id is required configuration."""

    provider = "anthropic"

    def __init__(self, model_id: str, max_tokens: int, system_prompt: str):
        import anthropic  # imported lazily so the core has no vendor dependency

        self.model_id = model_id
        self._client = anthropic.Anthropic()
        self._max_tokens = max_tokens
        self._system = system_prompt

    def propose(self, role: str, context: Mapping[str, Any]) -> dict[str, Any]:
        message = self._client.messages.create(
            model=self.model_id,
            max_tokens=self._max_tokens,
            system=self._system,
            messages=[{"role": "user", "content": json.dumps({"role": role, "context": context})}],
        )
        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        return json.loads(text)
