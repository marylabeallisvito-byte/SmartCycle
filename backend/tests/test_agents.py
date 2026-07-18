"""
SmartCycle — Router & Tools Tests
===================================

Tests for router classification and tool functions.
"""
import asyncio
from typing import Dict

from app.agents import router_node, quantitative_researcher_node
from app.schema import AgentState
from app.tools import fetch_market_data, hybrid_retrieve, web_search
from tests.conftest import make_base_state


# ═══════════════════════════════════════════════════════════════
# Router Node Tests
# ═══════════════════════════════════════════════════════════════

def test_router_classifies_data_fetching():
    """Verify router classifies ticker queries as data_fetching."""
    state = make_base_state(query="What is the current price of 600519?")
    result = asyncio.run(router_node(state))
    assert result["query_category"] == "data_fetching"


def test_router_classifies_research():
    """Verify router classifies analysis queries as research."""
    state = make_base_state(query="Analyze the EV battery sector outlook for 2025")
    result = asyncio.run(router_node(state))
    assert result["query_category"] == "research"


def test_router_classifies_emotional():
    """Verify router classifies emotional queries."""
    test_queries = [
        "I'm panicking about my stock losses",
        "我亏了很多钱睡不着觉",
        "I'm worried about the market crash",
        "最近亏了好多钱，好焦虑",
    ]
    for query in test_queries:
        state = make_base_state(query=query)
        result = asyncio.run(router_node(state))
        assert result["query_category"] == "emotional_support", f"Failed for: {query}"


def test_router_handles_empty():
    """Verify router handles empty query gracefully."""
    state = make_base_state(query="")
    result = asyncio.run(router_node(state))
    # Should fall back to a default category
    assert result["query_category"] in ("data_fetching", "research", "emotional_support")


def test_router_handles_chinese():
    """Verify router handles Chinese queries."""
    state = make_base_state(query="分析一下新能源板块")
    result = asyncio.run(router_node(state))
    assert result["query_category"] in ("data_fetching", "research", "emotional_support")


# ═══════════════════════════════════════════════════════════════
# Quantitative Researcher Node Tests
# ═══════════════════════════════════════════════════════════════

def test_researcher_extracts_ticker():
    """Verify researcher extracts ticker from query."""
    state = make_base_state(query="What is the P/E of 600519?")
    state["query_category"] = "data_fetching"
    result = asyncio.run(quantitative_researcher_node(state))
    raw_data = result.get("raw_data", {})
    assert "extracted_ticker" in raw_data
    assert raw_data["extracted_ticker"] == "600519"


def test_researcher_fetches_market_data():
    """Verify researcher fetches market data for the extracted ticker."""
    state = make_base_state(query="How is the CSI 300 performing?")
    state["query_category"] = "research"
    result = asyncio.run(quantitative_researcher_node(state))
    raw_data = result.get("raw_data", {})
    assert "market_data" in raw_data
    assert raw_data["market_data"] is not None


def test_researcher_retrieves_rag_context():
    """Verify researcher retrieves RAG document context."""
    state = make_base_state(query="What is the outlook for lithium battery sector?")
    state["query_category"] = "research"
    result = asyncio.run(quantitative_researcher_node(state))
    raw_data = result.get("raw_data", {})
    assert "rag_context" in raw_data


def test_researcher_no_llm_output():
    """FinRobot principle: Researcher produces NO narrative text."""
    state = make_base_state(query="Check the CSI 300 P/E ratio")
    state["query_category"] = "data_fetching"
    result = asyncio.run(quantitative_researcher_node(state))
    # Researcher should NOT populate draft_response or final_response
    assert result.get("draft_response", "") == ""
    assert result.get("final_response", "") == ""


# ═══════════════════════════════════════════════════════════════
# Tools — fetch_market_data
# ═══════════════════════════════════════════════════════════════

def test_fetch_market_data_ashare():
    """Verify fetch_market_data returns data for A-share ticker."""
    data = fetch_market_data("600519")
    assert isinstance(data, dict)
    assert "symbol" in data
    assert "price" in data
    assert data["name_cn"] in ("贵州茅台", "")  # mock or real


def test_fetch_market_data_index():
    """Verify fetch_market_data returns data for CSI 300."""
    data = fetch_market_data("000300")
    assert isinstance(data, dict)
    assert "price" in data


def test_fetch_market_data_us():
    """Verify fetch_market_data returns data for US ticker."""
    data = fetch_market_data("NVDA")
    assert isinstance(data, dict)
    assert "symbol" in data


def test_fetch_market_data_unknown():
    """Verify fetch_market_data handles unknown symbols gracefully."""
    data = fetch_market_data("UNKNOWN_XYZ_999")
    assert isinstance(data, dict)
    # Should still return a dict (mock data or error info)


# ═══════════════════════════════════════════════════════════════
# Tools — hybrid_retrieve
# ═══════════════════════════════════════════════════════════════

def test_hybrid_retrieve_returns_results():
    """Verify hybrid_retrieve returns results for a query."""
    result = hybrid_retrieve("新能源电池产业链", top_k=3)
    assert result["status"] == "ok"
    assert len(result["results"]) > 0
    assert "snippet" in result["results"][0]


def test_hybrid_retrieve_empty_query():
    """Verify hybrid_retrieve handles empty query."""
    result = hybrid_retrieve("", top_k=3)
    assert result["status"] == "ok"


def test_hybrid_retrieve_respects_top_k():
    """Verify hybrid_retrieve respects the top_k parameter."""
    result = hybrid_retrieve("market outlook", top_k=2)
    assert len(result["results"]) <= 2


# ═══════════════════════════════════════════════════════════════
# Tools — web_search
# ═══════════════════════════════════════════════════════════════

def test_web_search_returns_list():
    """Verify web_search returns a list (may be empty if network unavailable)."""
    results = web_search("CSI 300 ETF flows")
    assert isinstance(results, list)


# Run all tests when executed directly
if __name__ == "__main__":
    tests = [
        test_router_classifies_data_fetching,
        test_router_classifies_research,
        test_router_classifies_emotional,
        test_router_handles_empty,
        test_router_handles_chinese,
        test_researcher_extracts_ticker,
        test_researcher_fetches_market_data,
        test_researcher_retrieves_rag_context,
        test_researcher_no_llm_output,
        test_fetch_market_data_ashare,
        test_fetch_market_data_index,
        test_fetch_market_data_us,
        test_fetch_market_data_unknown,
        test_hybrid_retrieve_returns_results,
        test_hybrid_retrieve_empty_query,
        test_hybrid_retrieve_respects_top_k,
        test_web_search_returns_list,
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
