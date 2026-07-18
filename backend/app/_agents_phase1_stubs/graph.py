"""
SmartCycle — LangGraph Agent Graph Definition

Multi-agent workflow:
  User Query → Market Analyst → Portfolio Advisor → Compliance Checker → Response
"""

from typing import TypedDict

from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    """Shared state passed between agent nodes."""
    query: str
    user_profile: dict | None
    market_data: dict | None
    portfolio_advice: str | None
    compliance_report: dict | None
    final_response: str | None


# TODO: Build the full graph in Phase 2
# workflow = StateGraph(AgentState)
# workflow.add_node("market_analyst", market_analyst_node)
# workflow.add_node("portfolio_advisor", portfolio_advisor_node)
# workflow.add_node("compliance_checker", compliance_checker_node)
# workflow.set_entry_point("market_analyst")
# ...
# app_graph = workflow.compile()
