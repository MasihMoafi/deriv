"""Model boundary for one-ticket-at-a-time classification."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any

from .contracts import CATEGORY_VALUES, PRIORITY_VALUES, SENTIMENT_VALUES

PROMPT_VERSION = "ticket-classification-v1"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-5.6-luna"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class ClassificationResult:
    prediction: dict[str, Any]
    provider: str
    model: str
    fallback: bool


class LLMAdapter:
    """Use OpenRouter when configured, otherwise an explicitly visible fallback."""

    def __init__(
        self,
        provider: str = "local",
        model: str = "local-deterministic",
        api_key: str | None = None,
        endpoint: str = OPENROUTER_ENDPOINT,
        timeout: float = 30.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout

    @classmethod
    def from_environment(cls, requested: str | None = None) -> "LLMAdapter":
        selected = (requested or os.getenv("TICKET_LLM_PROVIDER", "auto")).lower()
        key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        endpoint = os.getenv("OPENROUTER_ENDPOINT", OPENROUTER_ENDPOINT)
        if selected == "local":
            return cls(provider="local-fallback", model="local-deterministic")
        if selected in {"auto", "openrouter"} and key and model:
            return cls(provider="openrouter", model=model, api_key=key, endpoint=endpoint)
        if selected == "openrouter":
            # Missing credentials/configuration is an explicit reason to select
            # the local path; no pretend live-provider result is emitted.
            return cls(provider="local-fallback", model="local-deterministic")
        return cls(provider="local-fallback", model="local-deterministic")

    def classify(self, ticket: dict[str, Any]) -> ClassificationResult:
        if self.provider == "openrouter":
            try:
                prediction = self._request_openrouter(ticket)
                return ClassificationResult(prediction, self.provider, self.model, False)
            except Exception:
                # The request has already happened (or failed before a response).
                # Keep the result inspectable and mark it as fallback output.
                fallback = self._local_prediction(ticket)
                return ClassificationResult(
                    fallback, "local-fallback-after-openrouter-error", "local-deterministic", True
                )
        return ClassificationResult(
            self._local_prediction(ticket), self.provider, self.model, True
        )

    def _request_openrouter(self, ticket: dict[str, Any]) -> dict[str, Any]:
        system = (
            "Return JSON only, with exactly these fields: ticket_id (string), "
            "category (one of payment_issue, account_verification, login_access, "
            "trading_problem, other), priority (one of low, medium, high), "
            "sentiment (one of neutral, frustrated, urgent), and reasoning (a short, "
            "human-readable string)."
        )
        # The user message contains the original ticket fields and no labels or
        # scoring guidance.
        user = json.dumps(ticket, ensure_ascii=False, sort_keys=True)
        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/ticket-evaluation",
                "X-Title": "Replayable Ticket Evaluation",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        content = envelope["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(str(part.get("text", "")) for part in content)
        if not isinstance(content, str):
            raise ValueError("OpenRouter content was not text")
        return _decode_json_object(content)

    @staticmethod
    def _local_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
        text = f"{ticket.get('subject', '')} {ticket.get('message', '')}".lower()
        category = "other"
        if any(word in text for word in ("payment", "card", "charged", "refund", "cash")):
            category = "payment_issue"
        elif any(word in text for word in ("verify", "verification", "identity", "document")):
            category = "account_verification"
        elif any(word in text for word in ("login", "log in", "sign in", "password", "access")):
            category = "login_access"
        elif any(word in text for word in ("trade", "trading", "order", "position")):
            category = "trading_problem"

        priority = "low"
        if any(word in text for word in ("urgent", "immediately", "blocked", "cannot", "can't")):
            priority = "high"
        elif any(word in text for word in ("soon", "unable", "failed", "declined", "error")):
            priority = "medium"

        sentiment = "neutral"
        if any(word in text for word in ("urgent", "immediately", "emergency")):
            sentiment = "urgent"
        elif any(word in text for word in ("angry", "frustrated", "failed", "declined", "error", "can't")):
            sentiment = "frustrated"

        return {
            "ticket_id": ticket.get("ticket_id", ""),
            "category": category if category in CATEGORY_VALUES else "other",
            "priority": priority if priority in PRIORITY_VALUES else "low",
            "sentiment": sentiment if sentiment in SENTIMENT_VALUES else "neutral",
            "reasoning": "Deterministic local fallback classification from ticket text.",
        }


def _decode_json_object(content: str) -> dict[str, Any]:
    """Decode JSON, allowing only local removal of common markdown fences."""
    candidate = content.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    decoded = json.loads(candidate)
    if not isinstance(decoded, dict):
        raise ValueError("prediction JSON must be an object")
    return decoded
