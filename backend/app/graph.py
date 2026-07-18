"""
SmartCycle — Graph Orchestration Layer
========================================

This module compiles the agent pipeline.  It uses LangGraph's StateGraph
when available (full checkpointing, streaming, conditional edges), and
falls back to a deterministic simple pipeline otherwise.

Architecture references:
  • FinRobot:     Nodes 1 & 2 are PURE COMPUTATION (no LLM).
                  Node 3 is the SOLE narrative generator.
  • tradingagents: The conditional edge at Node 4 enforces
                  adversarial compliance with a loop-back.

                         ┌──────────┐
                         │  START   │
                         └────┬─────┘
                              │
                    ┌─────────▼──────────┐
                    │  Node 1: ROUTER    │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Node 2: RESEARCHER│  ← FinRobot: deterministic tools ONLY
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
               ┌───│  Node 3: COPILOT   │←──────────────┐
               │   └─────────┬──────────┘                │
               │             │                            │
               │   ┌─────────▼──────────────┐             │
               │   │  Node 4: COMPLIANCE    │             │
               │   └────┬──────────┬────────┘             │
               │        │          │                       │
               │   passed      failed + iter < 3            │
               │        │          │                       │
               │        │          └──── retry ────────────┘
               │        │
               │   ┌────▼────┐
               │   │   END   │
               │   └─────────┘

Usage:
    from app.graph import smartcycle_graph
    result = await smartcycle_graph.ainvoke(initial_state)
"""

from typing import Any, Dict

from app.agents import (
    MAX_RETRIES,
    compliance_gatekeeper_node,
    empathy_copilot_node,
    quantitative_researcher_node,
    router_node,
)
from app.schema import AgentState

# ═══════════════════════════════════════════════════════════════
# Conditional Edge — Compliance Gate
# ═══════════════════════════════════════════════════════════════


def _should_retry(state: AgentState) -> bool:
    """Determine if the compliance loop should continue.

    tradingagents CONDITIONAL GATE:
      • True  → END     (release the cleaned response)
      • False → retry   (send revision_notes back to the Copilot)
      • False + max iter → END (force-override already applied)
    """
    passed: bool = state.get("compliance_passed", True)
    iteration: int = state.get("iteration_count", 0)
    if passed:
        return False
    return iteration < MAX_RETRIES


# ═══════════════════════════════════════════════════════════════
# LangGraph-backed implementation (preferred)
# ═══════════════════════════════════════════════════════════════

def _build_langgraph_graph():
    """Build a native LangGraph StateGraph with conditional edge support."""
    from typing import Literal

    from langgraph.graph import END, START, StateGraph  # type: ignore[import-untyped]

    def _route_after_compliance(state: AgentState) -> Literal["empathy_copilot", END]:
        passed: bool = state.get("compliance_passed", True)
        iteration: int = state.get("iteration_count", 0)
        if passed:
            return END
        if iteration < MAX_RETRIES:
            return "empathy_copilot"
        return END

    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("quantitative_researcher", quantitative_researcher_node)
    workflow.add_node("empathy_copilot", empathy_copilot_node)
    workflow.add_node("compliance_gatekeeper", compliance_gatekeeper_node)

    workflow.add_edge(START, "router")
    workflow.add_edge("router", "quantitative_researcher")
    workflow.add_edge("quantitative_researcher", "empathy_copilot")
    workflow.add_edge("empathy_copilot", "compliance_gatekeeper")

    workflow.add_conditional_edges(
        "compliance_gatekeeper",
        _route_after_compliance,
        {"empathy_copilot": "empathy_copilot", END: END},
    )

    return workflow.compile()


# ═══════════════════════════════════════════════════════════════
# Simple pipeline fallback (no LangGraph dependency)
# ═══════════════════════════════════════════════════════════════

class _SimplePipeline:
    """Deterministic sequential pipeline with compliance loop-back.

    Implements the same semantics as the LangGraph StateGraph:
      1. Router
      2. Quantitative Researcher
      3. Empathy Copilot
      4. Compliance Gatekeeper → (retry Copilot if failed, max 3x)

    Exposes the same .ainvoke(state) → state interface for drop-in compatibility.
    """

    nodes: Dict[str, Any]

    def __init__(self) -> None:
        self.nodes = {
            "router": router_node,
            "quantitative_researcher": quantitative_researcher_node,
            "empathy_copilot": empathy_copilot_node,
            "compliance_gatekeeper": compliance_gatekeeper_node,
        }

    async def ainvoke(self, state: AgentState) -> AgentState:
        """Execute the full pipeline asynchronously.

        Args:
            state: Initial AgentState (must have 'query' populated).

        Returns:
            Final AgentState with all channels populated.
        """
        current: AgentState = dict(state)  # type: ignore[arg-type]

        # ── Node 1: Router ──
        partial = await router_node(current)
        current.update(partial)  # type: ignore[arg-type]

        # ── Node 2: Quantitative Researcher ──
        partial = await quantitative_researcher_node(current)
        current.update(partial)  # type: ignore[arg-type]

        # ── Node 3 + 4: Copilot ⇄ Compliance loop ──
        while True:
            partial = await empathy_copilot_node(current)
            current.update(partial)  # type: ignore[arg-type]

            partial = await compliance_gatekeeper_node(current)
            current.update(partial)  # type: ignore[arg-type]

            if not _should_retry(current):
                break

        return current


# ═══════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════

try:
    smartcycle_graph = _build_langgraph_graph()
    _USING_LANGGRAPH = True
except (ImportError, Exception):
    smartcycle_graph = _SimplePipeline()
    _USING_LANGGRAPH = False
