"""
SmartCycle — Schema Validation Tests
======================================

Tests for Pydantic models and AgentState TypedDict in app/schema.py.
"""
from app.schema import (
    AIResponse,
    AdvisorQuery,
    ClientProfile,
    ComplianceFlag,
    QueryCategory,
    RiskTolerance,
    AnxietyLevel,
    InvestmentHorizon,
    KnowledgeLevel,
)


def test_query_category_enum():
    """Verify QueryCategory enum values."""
    assert QueryCategory.DATA_FETCHING.value == "data_fetching"
    assert QueryCategory.RESEARCH.value == "research"
    assert QueryCategory.EMOTIONAL_SUPPORT.value == "emotional_support"


def test_risk_tolerance_enum():
    """Verify RiskTolerance enum values."""
    assert RiskTolerance.CONSERVATIVE.value == "conservative"
    assert RiskTolerance.MODERATE.value == "moderate"
    assert RiskTolerance.AGGRESSIVE.value == "aggressive"


def test_anxiety_level_enum():
    """Verify AnxietyLevel enum values."""
    assert AnxietyLevel.LOW.value == "low"
    assert AnxietyLevel.MEDIUM.value == "medium"
    assert AnxietyLevel.HIGH.value == "high"


def test_client_profile_defaults():
    """Verify ClientProfile default values."""
    profile = ClientProfile()
    assert profile.risk_tolerance == RiskTolerance.MODERATE
    assert profile.anxiety_level == AnxietyLevel.MEDIUM
    assert profile.investment_horizon == InvestmentHorizon.MEDIUM
    assert profile.knowledge_level == KnowledgeLevel.BEGINNER


def test_client_profile_custom():
    """Verify ClientProfile with custom values."""
    profile = ClientProfile(
        risk_tolerance=RiskTolerance.CONSERVATIVE,
        anxiety_level=AnxietyLevel.HIGH,
        investment_horizon=InvestmentHorizon.SHORT,
        knowledge_level=KnowledgeLevel.BEGINNER,
        age_range="25-35",
        portfolio_value_yuan=500_000.0,
    )
    assert profile.risk_tolerance == RiskTolerance.CONSERVATIVE
    assert profile.age_range == "25-35"
    assert profile.portfolio_value_yuan == 500_000.0


def test_client_profile_age_validation():
    """Verify age_range validation: increasing order required."""
    profile = ClientProfile(age_range="25-35")
    assert profile.age_range == "25-35"

    # Invalid: decreasing order should raise
    try:
        ClientProfile(age_range="35-25")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected


def test_client_profile_to_dict():
    """Verify to_dict() serialization for AgentState compatibility."""
    profile = ClientProfile(
        risk_tolerance=RiskTolerance.AGGRESSIVE,
        anxiety_level=AnxietyLevel.LOW,
        knowledge_level=KnowledgeLevel.ADVANCED,
    )
    d = profile.to_dict()
    assert d["risk_tolerance"] == "aggressive"
    assert d["anxiety_level"] == "low"
    assert d["knowledge_level"] == "advanced"


def test_advisor_query_validation():
    """Verify AdvisorQuery validation."""
    # Valid
    q = AdvisorQuery(query="What is the CSI 300 outlook?")
    assert q.query == "What is the CSI 300 outlook?"

    # Empty query should fail
    try:
        AdvisorQuery(query="")
        assert False, "Should have raised ValueError"
    except Exception:
        pass

    # Whitespace-only should fail
    try:
        AdvisorQuery(query="   ")
        assert False, "Should have raised ValueError"
    except Exception:
        pass


def test_advisor_query_with_profile():
    """Verify AdvisorQuery with client profile."""
    profile = ClientProfile(risk_tolerance=RiskTolerance.CONSERVATIVE)
    q = AdvisorQuery(
        query="Should I sell my stocks?",
        client_profile=profile,
        conversation_id="conv-001",
    )
    assert q.query == "Should I sell my stocks?"
    assert q.client_profile is not None
    assert q.client_profile.risk_tolerance == RiskTolerance.CONSERVATIVE
    assert q.conversation_id == "conv-001"


def test_ai_response_construction():
    """Verify AIResponse can be constructed with all fields."""
    response = AIResponse(
        query_category="research",
        raw_data={"market_data": {"000300": {"price": 3987.45}}},
        draft_response="沪深300目前估值处于历史中位水平...",
        compliance_passed=True,
        compliance_flags=[],
        revision_count=0,
        final_response="沪深300目前估值处于历史中位水平...\n\n⚠️ 风险提示...",
        disclaimer="⚠️ 风险提示：投资有风险...",
        latency_ms=1234.56,
        conversation_id="conv-001",
    )
    assert response.query_category == "research"
    assert response.compliance_passed is True
    assert response.latency_ms == 1234.56
    assert "风险提示" in response.final_response


def test_compliance_flag_model():
    """Verify ComplianceFlag model."""
    flag = ComplianceFlag(
        rule="BANNED_TERM:guaranteed",
        severity="critical",
        banned_phrase="guaranteed",
        suggestion="Replace with 'historically'.",
    )
    assert flag.severity == "critical"
    assert flag.banned_phrase == "guaranteed"


def test_agent_state_typed_dict():
    """Verify AgentState TypedDict structure."""
    from app.schema import AgentState

    state: AgentState = {
        "query": "test",
        "client_profile": None,
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
    assert state["query"] == "test"
    assert state["compliance_passed"] is True


# Run all tests when executed directly
if __name__ == "__main__":
    tests = [
        test_query_category_enum,
        test_risk_tolerance_enum,
        test_anxiety_level_enum,
        test_client_profile_defaults,
        test_client_profile_custom,
        test_client_profile_age_validation,
        test_client_profile_to_dict,
        test_advisor_query_validation,
        test_advisor_query_with_profile,
        test_ai_response_construction,
        test_compliance_flag_model,
        test_agent_state_typed_dict,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
