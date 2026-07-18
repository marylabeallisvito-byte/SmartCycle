"""
SmartCycle — Test Fixtures & Configuration
===========================================

Shared test fixtures for the SmartCycle test suite.

Works both with pytest (when installed) and standalone runner (run_tests.py).
"""

from typing import Any, Dict, List

from app.schema import AgentState


def make_base_state(
    query: str = "What is the P/E ratio of 600519?",
    risk_tolerance: str = "moderate",
    anxiety_level: str = "medium",
    investment_horizon: str = "medium",
    knowledge_level: str = "intermediate",
) -> AgentState:
    """Build a standard AgentState for testing.

    All fields are populated with sensible defaults so individual
    tests can override only what they need.
    """
    return {
        "query": query,
        "client_profile": {
            "risk_tolerance": risk_tolerance,
            "anxiety_level": anxiety_level,
            "investment_horizon": investment_horizon,
            "knowledge_level": knowledge_level,
        },
        "query_category": "",
        "raw_data": {},
        "draft_response": "",
        "compliance_passed": True,
        "compliance_report": {},
        "revision_notes": [],
        "final_response": "",
        "disclaimer": "",
        "iteration_count": 0,
        "latency_ms": 0.0,
        "timestamp": "",
    }


def make_anxious_state() -> AgentState:
    """Build a state for a high-anxiety conservative investor."""
    return make_base_state(
        query="I'm panicking about my losses, should I sell everything?",
        risk_tolerance="conservative",
        anxiety_level="high",
        knowledge_level="beginner",
    )


def make_aggressive_state() -> AgentState:
    """Build a state for a low-anxiety aggressive investor."""
    return make_base_state(
        query="What options strategies can I use to maximize leverage?",
        risk_tolerance="aggressive",
        anxiety_level="low",
        knowledge_level="advanced",
    )


# Try to register as pytest fixtures (ignored if pytest not installed)
try:
    import pytest

    @pytest.fixture
    def base_state() -> AgentState:
        return make_base_state()

    @pytest.fixture
    def anxious_state() -> AgentState:
        return make_anxious_state()

    @pytest.fixture
    def aggressive_state() -> AgentState:
        return make_aggressive_state()

except ImportError:
    pass  # pytest not installed — fixtures are available as plain functions
