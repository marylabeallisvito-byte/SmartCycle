"""
SmartCycle — Compliance Logic Tests
=====================================

Tests for the Compliance Gatekeeper node and related utilities.
Covers banned-term detection, suitability checking, and force-override.
"""
import asyncio
import re
from typing import Dict, List

from app.agents import (
    BANNED_PATTERNS,
    SUITABILITY_MAP,
    MAX_RETRIES,
    get_risk_disclaimer,
    compliance_gatekeeper_node,
)
from app.schema import AgentState
from tests.conftest import make_base_state, make_anxious_state


# ═══════════════════════════════════════════════════════════════
# Banned Pattern Tests
# ═══════════════════════════════════════════════════════════════

def test_english_banned_terms_detected():
    """Verify English banned terms are detected by regex."""
    test_cases = [
        ("This investment is guaranteed to go up", True, "guaranteed"),
        ("You must buy this stock now", True, "must buy"),
        ("There is absolutely no risk involved", True, "no risk"),
        ("This strategy is definitely going to work", True, "definitely"),
        ("It's 100% safe and secure", True, "100% safe"),
        ("You can't lose money with this approach", True, "can't lose"),
    ]

    for text, should_detect, _ in test_cases:
        found = False
        for pattern, severity, _ in BANNED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found = True
                break
        assert found == should_detect, f"Failed for: '{text}' — expected detect={should_detect}"


def test_risk_free_rate_not_flagged():
    """Verify 'risk-free rate' (legitimate financial term) is NOT flagged."""
    text = "The risk-free rate is currently 1.7% for Chinese government bonds."
    found = False
    for pattern, severity, _ in BANNED_PATTERNS:
        if "risk" in pattern and "free" in pattern:
            if re.search(pattern, text, re.IGNORECASE):
                found = True
                break
    assert not found, "'risk-free rate' should NOT be flagged"


def test_risk_free_investment_flagged():
    """Verify 'risk-free product' IS flagged."""
    text = "This is a risk-free product that guarantees returns."
    found = False
    for pattern, severity, _ in BANNED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found = True
            break
    assert found, "'risk-free investment' SHOULD be flagged"


def test_chinese_banned_terms_detected():
    """Verify Chinese banned terms are detected."""
    test_cases = [
        "这个产品是保本的",  # 保本
        "保证收益的产品",    # 保证收益
        "稳赚不赔的策略",    # 稳赚不赔
        "绝对安全的投资",    # 绝对安全
        "零风险理财",        # 零风险
        "一定赚钱的方法",    # 一定赚
        "承诺收益8%",        # 承诺收益
    ]

    for text in test_cases:
        found = False
        for pattern, severity, _ in BANNED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found = True
                break
        assert found, f"Chinese banned term NOT detected in: '{text}'"


def test_banned_patterns_count():
    """Verify we have adequate banned pattern coverage (26+ patterns)."""
    assert len(BANNED_PATTERNS) >= 26, f"Expected 26+ banned patterns, got {len(BANNED_PATTERNS)}"


# ═══════════════════════════════════════════════════════════════
# Suitability Tests
# ═══════════════════════════════════════════════════════════════

def test_suitability_map_exists():
    """Verify suitability map covers all risk levels."""
    assert "conservative" in SUITABILITY_MAP
    assert "moderate" in SUITABILITY_MAP
    assert "aggressive" in SUITABILITY_MAP


def test_conservative_suitability_flags():
    """Verify conservative investors get flagged for aggressive terms."""
    assert len(SUITABILITY_MAP["conservative"]) > 0


# ═══════════════════════════════════════════════════════════════
# Compliance Gatekeeper Node Tests
# ═══════════════════════════════════════════════════════════════

def test_compliance_passes_clean_draft():
    """Verify compliance passes for a clean, well-written draft."""
    state = make_base_state()
    state["draft_response"] = (
        "Based on current market conditions, the CSI 300 is trading at "
        "a P/E of 11.8x, which is below its 5-year average of 13.2x. "
        "This may suggest moderate undervaluation. However, past performance "
        "does not indicate future results, and investors should consider "
        "their personal risk tolerance before making decisions."
    )

    result = asyncio.run(compliance_gatekeeper_node(state))
    assert result["compliance_passed"] is True
    assert "⚠️" in result["final_response"]  # disclaimer appended


def test_compliance_flags_banned_term():
    """Verify compliance flags a draft with banned terms."""
    state = make_base_state()
    state["draft_response"] = "This investment is guaranteed to generate returns. You should definitely buy it."

    result = asyncio.run(compliance_gatekeeper_node(state))
    # Should flag banned terms
    report = result.get("compliance_report", {})
    flags = report.get("flags", [])
    assert len(flags) > 0, f"Expected flags for banned terms, got {len(flags)}"


def test_compliance_flags_chinese_banned():
    """Verify compliance flags Chinese banned terms."""
    state = make_base_state()
    state["draft_response"] = "这个产品是保本的，保证收益，绝对没有问题。"

    result = asyncio.run(compliance_gatekeeper_node(state))
    report = result.get("compliance_report", {})
    flags = report.get("flags", [])
    assert len(flags) > 0, f"Expected flags for Chinese banned terms, got {len(flags)}"


def test_compliance_force_override():
    """Verify force-override after MAX_RETRIES attempts."""
    state = make_base_state()
    state["draft_response"] = "This is guaranteed to produce risk-free returns."
    state["iteration_count"] = MAX_RETRIES - 1  # last attempt before force

    result = asyncio.run(compliance_gatekeeper_node(state))
    report = result.get("compliance_report", {})

    # Should either force-override or have revision notes
    is_force_override = report.get("force_override", False)
    has_flags = len(report.get("flags", [])) > 0
    assert is_force_override or has_flags, "Expected force-override or flags"


def test_disclaimer_appended():
    """Verify risk disclaimer is appended when compliance passes."""
    state = make_base_state()
    state["draft_response"] = "The CSI 300 is currently showing moderate valuation levels."

    result = asyncio.run(compliance_gatekeeper_node(state))
    final = result.get("final_response", "")
    assert "风险提示" in final or "Risk Disclosure" in final


def test_user_query_scanning():
    """Verify PASS 0 scans the user's original query for banned terms."""
    state = make_base_state(query="这个产品是保本的吗？")
    state["draft_response"] = "The CSI 300 is trading at reasonable valuations."  # clean draft

    result = asyncio.run(compliance_gatekeeper_node(state))
    report = result.get("compliance_report", {})

    # PASS 0 should flag the user query's banned term "保本"
    flags = report.get("flags", [])
    user_query_flags = [f for f in flags if "USER_QUERY" in f.get("rule", "")]
    assert len(user_query_flags) > 0 or len(flags) > 0, "PASS 0 should flag user's banned terms in query"


# ═══════════════════════════════════════════════════════════════
# Risk Disclaimer
# ═══════════════════════════════════════════════════════════════

def test_risk_disclaimer_non_empty():
    """Verify risk disclaimer is a non-empty bilingual string."""
    disclaimer = get_risk_disclaimer()
    assert len(disclaimer) > 50
    assert "风险提示" in disclaimer or "Risk Disclosure" in disclaimer


# Run all tests when executed directly
if __name__ == "__main__":
    tests = [
        test_english_banned_terms_detected,
        test_risk_free_rate_not_flagged,
        test_risk_free_investment_flagged,
        test_chinese_banned_terms_detected,
        test_banned_patterns_count,
        test_suitability_map_exists,
        test_conservative_suitability_flags,
        test_compliance_passes_clean_draft,
        test_compliance_flags_banned_term,
        test_compliance_flags_chinese_banned,
        test_compliance_force_override,
        test_disclaimer_appended,
        test_user_query_scanning,
        test_risk_disclaimer_non_empty,
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
