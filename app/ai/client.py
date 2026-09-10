"""Thin client for a locally operated, OpenAI-compatible inference server.

Deliberately uses only the generic /chat/completions HTTP contract (via
httpx) instead of a vendor-specific SDK, so that Ollama, llama.cpp server,
LM Studio, or any other compatible server can be swapped in purely through
configuration (MODEL_BASE_URL / MODEL_NAME), with no code changes.
"""
import json
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger("aise.ai.client")


class InferenceError(Exception):
    """Base class for all local-inference failures the caller must handle."""


class InferenceUnavailableError(InferenceError):
    """The inference server could not be reached at all."""


class InferenceTimeoutError(InferenceError):
    """The inference server did not respond within the configured timeout."""


class InvalidModelOutputError(InferenceError):
    """The model responded, but its output was not usable (malformed JSON,
    empty content, or otherwise not parseable by the caller)."""


@dataclass
class ChatResult:
    content: str
    latency_seconds: float


class LocalLLMClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.model_base_url,
            timeout=settings.model_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.model_api_key}"},
        )

    def close(self) -> None:
        self._client.close()

    def chat(self, system_prompt: str, user_prompt: str, *, json_mode: bool = True) -> ChatResult:
        """Call the chat/completions endpoint. Raises a typed InferenceError
        subclass on any failure so callers can react appropriately instead of
        the request silently producing garbage.
        """
        payload = {
            "model": self._settings.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        attempts = self._settings.model_max_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            start = time.monotonic()
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                last_error = InferenceTimeoutError(str(exc))
            except httpx.ConnectError as exc:
                last_error = InferenceUnavailableError(str(exc))
            except httpx.HTTPError as exc:
                last_error = InferenceUnavailableError(str(exc))
            else:
                latency = time.monotonic() - start
                if response.status_code >= 500:
                    last_error = InferenceUnavailableError(
                        f"inference server returned {response.status_code}"
                    )
                elif response.status_code >= 400:
                    # Client error (e.g. unknown model): retrying won't help.
                    raise InvalidModelOutputError(
                        f"inference server rejected request: {response.status_code} {response.text[:300]}"
                    )
                else:
                    try:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                        raise InvalidModelOutputError(f"unexpected response shape: {exc}") from exc
                    return ChatResult(content=content, latency_seconds=latency)

            logger.warning("inference attempt %s/%s failed: %s", attempt + 1, attempts, last_error)

        assert last_error is not None
        raise last_error
