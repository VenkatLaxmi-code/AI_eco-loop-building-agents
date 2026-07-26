"""
Open-source LLM client.

Supports two provider modes, selected via LLM_PROVIDER in .env:

  - "ollama"            -> talks to a local Ollama server's /api/chat endpoint
                           (default: http://localhost:11434). Works out of the
                           box with any pulled open model (qwen2.5, llama3.1,
                           mistral, etc).
  - "openai_compatible" -> talks to any self-hosted server that implements the
                           OpenAI /v1/chat/completions schema (vLLM, LM Studio,
                           text-generation-webui, LocalAI, ...).

No proprietary hosted LLM (OpenAI, Gemini, Claude, ...) is required or used.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from app.config import settings

logger = logging.getLogger("llm_client")


class LLMConnectionError(RuntimeError):
    """Raised when the configured LLM endpoint cannot be reached at all."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM responds but the content cannot be parsed as JSON."""


class LLMClient:
    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider or settings.llm.provider
        self.base_url = (base_url or settings.llm.base_url).rstrip("/")
        self.model = model or settings.llm.model
        self.timeout_seconds = timeout_seconds or settings.llm.timeout_seconds
        self.api_key = api_key or settings.llm.api_key

    # ------------------------------------------------------------------
    def check_connection(self) -> bool:
        """Used by scripts/check_setup.py to verify the LLM is reachable."""
        try:
            if self.provider == "ollama":
                resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
                resp.raise_for_status()
                tags = [m.get("name", "") for m in resp.json().get("models", [])]
                found = any(self.model.split(":")[0] in t for t in tags)
                if not found:
                    logger.warning(
                        "Ollama is reachable but model '%s' was not found in "
                        "'ollama list'. Run: ollama pull %s", self.model, self.model
                    )
                return True
            else:
                resp = requests.get(f"{self.base_url}/models", timeout=5)
                return resp.status_code < 500
        except requests.RequestException as exc:
            logger.error("LLM connection check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1.5),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/api/chat"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        resp = requests.post(url, json=body, timeout=self.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1.5),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(url, headers=headers, json=body, timeout=self.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    def generate_decision_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Calls the configured LLM and returns the parsed JSON decision object.
        Raises LLMConnectionError if the server is unreachable, or
        LLMResponseError if the response cannot be parsed as JSON - callers
        (BuildingAgent) are expected to catch these and fall back to the
        deterministic fallback controller.
        """
        try:
            if self.provider == "ollama":
                raw = self._call_ollama(system_prompt, user_prompt)
            else:
                raw = self._call_openai_compatible(system_prompt, user_prompt)
        except requests.RequestException as exc:
            raise LLMConnectionError(f"Could not reach LLM at {self.base_url}: {exc}") from exc

        raw = raw.strip()
        # Some open models wrap JSON in markdown fences despite instructions; strip defensively.
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned non-JSON content: %s", raw[:300])
            raise LLMResponseError(f"LLM response was not valid JSON: {exc}") from exc
