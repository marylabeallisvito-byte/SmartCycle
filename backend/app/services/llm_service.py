"""
SmartCycle — LLM Service
==========================

Higher-level LLM operations with retry logic, token estimation,
and streaming support. Wraps app.llm for the service layer.

Python 3.9 compatible — no PEP 604 union syntax.
"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.llm import get_llm, is_real_llm
from app.schema import AgentState

logger = logging.getLogger("smartcycle.services.llm")

# Token estimation: ~4 chars per token for Chinese, ~4 chars for English
_CHARS_PER_TOKEN = 4


class LLMService:
    """LLM generation service with retry, token counting, and streaming.

    Usage:
        svc = LLMService()
        reply = await svc.generate(messages)
        async for chunk in svc.stream(messages):
            print(chunk, end="")
    """

    def __init__(self) -> None:
        self._llm = get_llm()
        self._is_real = is_real_llm()

    # ── Public API ──────────────────────────────────────────

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        raise_on_error: bool = False,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts.
            temperature: Optional temperature override.
            max_tokens: Optional max_tokens override.
            raise_on_error: If True, re-raise exceptions for the retry layer
                            to handle. If False (default), return "" on error
                            for backward compatibility.

        Returns:
            The LLM's text response, or empty string on error (unless raise_on_error=True).

        Raises:
            Exception: Only when raise_on_error=True and the LLM call fails.
        """
        try:
            response = await self._llm.chat(messages)
            return response
        except Exception as exc:
            logger.error("[llm_service] Generation failed: %s", exc)
            if raise_on_error:
                raise
            return ""

    async def generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 2,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate with automatic retry on transient failures.

        Args:
            messages: Chat messages list.
            max_retries: Maximum retry attempts (default 2).
            temperature: Optional temperature override.

        Returns:
            LLM response text, or empty string after all retries exhausted.
        """
        last_error: Optional[str] = None
        for attempt in range(max_retries + 1):
            try:
                # Use raise_on_error=True so exceptions propagate to this handler
                result = await self.generate(messages, temperature=temperature, raise_on_error=True)
                if result:
                    return result
                if attempt < max_retries:
                    logger.info("[llm_service] Empty response, retry %d/%d", attempt + 1, max_retries)
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    logger.warning("[llm_service] Attempt %d failed: %s, retrying...", attempt + 1, exc)

        logger.error("[llm_service] All %d attempts failed. Last error: %s", max_retries + 1, last_error)
        return ""

    async def stream(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM (yield chunks as they arrive).

        NOTE: Current httpx-based OpenAILikeLLM does not support true streaming.
        This method simulates streaming by yielding the full response in chunks.
        When real streaming is available (SSE), replace this implementation.

        Args:
            messages: Chat messages list.

        Yields:
            Text chunks of the response.
        """
        full_response = await self.generate(messages)
        if not full_response:
            yield ""
            return

        # Simulate streaming: yield in ~20-character chunks
        chunk_size = 20
        for i in range(0, len(full_response), chunk_size):
            yield full_response[i:i + chunk_size]

    # ── Token Estimation ────────────────────────────────────

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count for a text string.

        Rough approximation: 4 characters ≈ 1 token for mixed Chinese/English.
        For production use, replace with tiktoken or the provider's tokenizer.
        """
        if not text:
            return 0
        return max(1, len(text) // _CHARS_PER_TOKEN)

    @staticmethod
    def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
        """Estimate total token count for a messages list."""
        total = 0
        for msg in messages:
            total += LLMService.estimate_tokens(msg.get("content", ""))
        return total

    # ── Helpers ─────────────────────────────────────────────

    @property
    def is_real_llm(self) -> bool:
        """True if a real LLM backend is configured (vs mock)."""
        return self._is_real
