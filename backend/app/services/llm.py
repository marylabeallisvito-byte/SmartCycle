"""
SmartCycle — LLM Service (re-export)

This module is superseded. Import from the canonical locations instead:

    from app.llm import get_llm, is_real_llm, OpenAILikeLLM, MockLLM
    from app.services.llm_service import LLMService

This file remains as a backward-compatibility re-export only.
"""

# Re-export for backward compatibility
from app.llm import get_llm, is_real_llm, MockLLM, OpenAILikeLLM  # noqa: E402, F401
from app.services.llm_service import LLMService  # noqa: E402, F401
