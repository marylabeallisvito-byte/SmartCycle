"""
SmartCycle — LLM Abstraction Layer
===================================

Provides a unified async interface to any OpenAI-compatible API
(DeepSeek, Zhipu GLM, Qwen, OpenAI, etc.) via httpx.

Architecture:
  • get_llm()      → factory that returns the appropriate LLM backend
  • OpenAILikeLLM  → async httpx client for /chat/completions endpoints
  • MockLLM        → fallback when no API key is configured

Configuration (environment variables):
  LLM_API_KEY   → API key (required for real LLM)
  LLM_BASE_URL  → Base URL, e.g. https://api.deepseek.com/v1
  LLM_MODEL     → Model name, e.g. deepseek-chat
  LLM_TEMPERATURE → Default 0.3

Usage:
    from app.llm import get_llm
    llm = get_llm()
    reply = await llm.chat([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ])
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("smartcycle.llm")


# ═══════════════════════════════════════════════════════════════
# .env file loader (avoids dependency on python-dotenv)
# ═══════════════════════════════════════════════════════════════

def _load_env_file() -> None:
    """Load environment variables from backend/.env (if it exists).

    Searches upward from this file's directory to find the .env file.
    Simple KEY=VALUE parser — ignores comments and blank lines.
    """
    current = Path(__file__).resolve().parent  # backend/app/
    for _ in range(3):  # check app/, backend/, root/
        env_path = current / ".env"
        if env_path.is_file():
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:  # never override existing env vars
                        os.environ[key] = value
            logger.debug("[llm] Loaded .env from %s", env_path)
            return
        current = current.parent


_load_env_file()

# ═══════════════════════════════════════════════════════════════
# Config defaults
# ═══════════════════════════════════════════════════════════════

_LLM_API_KEY = os.getenv("LLM_API_KEY", "")
_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
_LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
_LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
_LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
_LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "45.0"))


# ═══════════════════════════════════════════════════════════════
# Real LLM backend (OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════

class OpenAILikeLLM:
    """Async LLM client for any OpenAI-compatible /chat/completions endpoint.

    Tested with: DeepSeek, Zhipu GLM, Qwen, OpenAI.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: float = 45.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

        # Normalise base_url — ensure it ends with /chat/completions
        url = base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        self._endpoint = url

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            trust_env=False,  # Bypass system proxy settings
        )

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send a chat completion request and return the text response.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts.

        Returns:
            The model's text reply.

        Raises:
            httpx.HTTPError: On network or API errors.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

        logger.info("[llm] → %s  model=%s  messages=%d", self._endpoint, self._model, len(messages))

        response = await self._client.post(self._endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        # OpenAI-compatible response format
        try:
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("[llm] Unexpected response shape: %s", exc)
            raise ValueError(f"Unexpected LLM response format: {exc}") from exc

        logger.info("[llm] ← %d chars", len(content))
        return content

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._client.aclose()


# ═══════════════════════════════════════════════════════════════
# Mock LLM fallback (reuses existing template logic)
# ═══════════════════════════════════════════════════════════════

class MockLLM:
    """No-op LLM that returns a sentinel so callers can fall back to templates.

    This exists so the rest of the code can always call `await llm.chat()`
    without an `if mock vs real` branch at every call site.
    """

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Return empty string — caller should fall back to template logic."""
        return ""

    async def close(self) -> None:
        pass


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

_llm_singleton: Optional[OpenAILikeLLM] = None
_llm_initialized: bool = False


def get_llm() -> OpenAILikeLLM:
    """Return the configured LLM backend (singleton).

    If LLM_API_KEY is set, returns a real OpenAILikeLLM.
    Otherwise returns a MockLLM — callers should detect the empty response
    and fall back to template-based generation.
    """
    global _llm_singleton, _llm_initialized  # noqa: PLW0603

    if not _llm_initialized:
        _llm_initialized = True
        if _LLM_API_KEY:
            _llm_singleton = OpenAILikeLLM(
                api_key=_LLM_API_KEY,
                base_url=_LLM_BASE_URL,
                model=_LLM_MODEL,
                temperature=_LLM_TEMPERATURE,
                max_tokens=_LLM_MAX_TOKENS,
                timeout=_LLM_TIMEOUT,
            )
            logger.info("[llm] Using real LLM: %s @ %s", _LLM_MODEL, _LLM_BASE_URL)
        else:
            logger.info("[llm] No LLM_API_KEY set — using template-based mock")

    # Return MockLLM if no key configured
    if _llm_singleton is None:
        return MockLLM()  # type: ignore[return-value]

    return _llm_singleton


def is_real_llm() -> bool:
    """Return True if a real LLM backend is configured."""
    return _LLM_API_KEY != ""
