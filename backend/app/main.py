"""
SmartCycle — FastAPI Application Entry Point
==============================================

POST /api/v1/chat triggers the full LangGraph multi-agent pipeline:
  Router → Quantitative Researcher → Empathy Copilot → Compliance Gatekeeper
                                                          ↓
                                              [conditional: loop-back on failure]

Architecture references:
  • OpenBB / FinRAG  → structured data + hybrid retrieval (via tools.py)
  • FinRobot         → strict separation of computation vs. narrative
  • tradingagents    → adversarial compliance gate with conditional retry
"""

import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.graph import smartcycle_graph
from app.schema import (
    AIResponse,
    AdvisorQuery,
    AgentState,
    ClientProfile,
    ComplianceFlag,
)


# ═══════════════════════════════════════════════════════════════
# App Lifecycle
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle.

    On startup:
      - The LangGraph is compiled at module-load time (graph.py).
      - In Phase 3, we'll warm the vector store and pre-load models here.

    On shutdown:
      - Gracefully close DB connections, flush caches.
    """
    # STARTUP
    # TODO Phase 3: warm up vector store, pre-load embedding model
    yield
    # SHUTDOWN
    # TODO Phase 3: close DB pool, flush Redis


# ═══════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="SmartCycle API",
    description="金仕达·智循 — B2B2C Financial Intelligence & Wealth Management Platform",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════

@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Service health check — used by Docker Compose healthcheck."""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "phase": "Phase 2 — Multi-Agent LangGraph Engine",
    }


# ═══════════════════════════════════════════════════════════════
# Chat Endpoint — triggers the full multi-agent pipeline
# ═══════════════════════════════════════════════════════════════

@app.post("/api/v1/chat", response_model=AIResponse, tags=["Agent"])
async def chat(request: AdvisorQuery) -> AIResponse:
    """Process a financial query through the full multi-agent pipeline.

    PIPELINE:
      1. Router          → classify intent
      2. Quant Researcher→ fetch market data + RAG context (FinRobot: no LLM)
      3. Empathy Copilot → generate tone-calibrated narrative
      4. Compliance Gate → adversarial screening (tradingagents)
         ↳ if failed: loop back to Copilot with revision_notes (max 3 retries)
         ↳ if passed: append mandatory risk disclaimer

    Args:
        request: AdvisorQuery with query text and optional client_profile.

    Returns:
        AIResponse with query_category, raw_data, draft_response,
        compliance verdict, final_response, and disclaimer.
    """
    t_start = time.perf_counter()

    # ── Build initial AgentState from request ──
    profile_dict: Optional[dict] = None
    if request.client_profile is not None:
        profile_dict = request.client_profile.to_dict()

    initial_state: AgentState = {
        "query": request.query,
        "client_profile": profile_dict,
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

    # ── Invoke the LangGraph pipeline ──
    try:
        final_state = await smartcycle_graph.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent pipeline error: {exc}",
        ) from exc

    # ── Compute latency ──
    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    # ── Build the API response ──
    compliance_flags: List[ComplianceFlag] = []
    for flag_dict in final_state.get("compliance_report", {}).get("flags", []):
        compliance_flags.append(ComplianceFlag(**flag_dict))

    return AIResponse(
        query_category=final_state.get("query_category", ""),
        raw_data=final_state.get("raw_data", {}),
        draft_response=final_state.get("draft_response", ""),
        compliance_passed=bool(final_state.get("compliance_passed", True)),
        compliance_flags=compliance_flags,
        revision_count=final_state.get("iteration_count", 0),
        final_response=final_state.get("final_response", ""),
        disclaimer=final_state.get("disclaimer", ""),
        latency_ms=latency_ms,
        conversation_id=request.conversation_id,
    )


# ═══════════════════════════════════════════════════════════════
# Debug endpoint — inspect the graph structure
# ═══════════════════════════════════════════════════════════════

@app.get("/api/v1/graph/info", tags=["System"])
async def graph_info():
    """Return metadata about the compiled LangGraph.

    Useful for debugging and frontend introspection.
    """
    nodes = list(smartcycle_graph.nodes.keys()) if hasattr(smartcycle_graph, 'nodes') else []
    return {
        "framework": "LangGraph",
        "architecture": "FinRobot + tradingagents hybrid",
        "pipeline": [
            "Router (classification)",
            "Quantitative Researcher (tool-only, no LLM)",
            "Empathy Copilot (narrative generation)",
            "Compliance Gatekeeper (adversarial check + conditional loop-back)",
        ],
        "max_compliance_retries": 3,
        "nodes": nodes,
    }
