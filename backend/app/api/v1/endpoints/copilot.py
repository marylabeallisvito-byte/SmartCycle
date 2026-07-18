"""
SmartCycle — B-end Copilot Endpoints
======================================

AI-assisted advisory tools for financial professionals.

POST /api/v1/copilot/query
    Submit a research or portfolio query through the multi-agent pipeline.
    Returns AIResponse with compliance screening, market data, and RAG context.

POST /api/v1/copilot/portfolio/build
    Generate a model portfolio based on client profile and market conditions.
"""

import time
from typing import Any, Dict, List, Optional

from app.graph import smartcycle_graph
from app.schema import (
    AIResponse,
    AdvisorQuery,
    AgentState,
    ClientProfile,
    ComplianceFlag,
)

# FastAPI router (only used when fastapi is installed)
try:
    from fastapi import APIRouter, HTTPException
    router = APIRouter()
    _HAS_FASTAPI = True
except ImportError:
    APIRouter = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    router = None  # type: ignore[assignment]
    _HAS_FASTAPI = False


# ═══════════════════════════════════════════════════════════════
# Core Logic (shared between FastAPI and Tornado handlers)
# ═══════════════════════════════════════════════════════════════

async def process_copilot_query(
    query: str,
    client_profile: Optional[dict] = None,
    conversation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Process a B-end copilot query through the agent pipeline.

    B-end queries differ from C-end:
      - More detailed responses (higher complexity tolerance)
      - Advisor role context in the metadata
      - Preserved raw data for advisor review
    """
    t_start = time.perf_counter()

    # Enrich metadata for B-end context
    enriched_meta = dict(metadata or {})
    enriched_meta["channel"] = "b_end_copilot"
    enriched_meta["role"] = "advisor"

    # Build initial state
    initial_state: AgentState = {
        "query": query,
        "client_profile": client_profile,
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

    # Run pipeline
    final_state = await smartcycle_graph.ainvoke(initial_state)

    # Build compliance flags
    compliance_flags = []
    for flag_dict in final_state.get("compliance_report", {}).get("flags", []):
        compliance_flags.append(flag_dict)

    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    return {
        "query_category": final_state.get("query_category", ""),
        "raw_data": final_state.get("raw_data", {}),
        "draft_response": final_state.get("draft_response", ""),
        "compliance_passed": bool(final_state.get("compliance_passed", True)),
        "compliance_flags": compliance_flags,
        "revision_count": final_state.get("iteration_count", 0),
        "final_response": final_state.get("final_response", ""),
        "disclaimer": final_state.get("disclaimer", ""),
        "latency_ms": latency_ms,
        "conversation_id": conversation_id,
        "timestamp": final_state.get("timestamp", ""),
    }


# ═══════════════════════════════════════════════════════════════
# FastAPI Endpoints
# ═══════════════════════════════════════════════════════════════

if _HAS_FASTAPI:

    @router.get("/")
    async def copilot_root():
        """Copilot service status."""
        return {
            "service": "copilot",
            "status": "operational",
            "version": "0.3.0",
            "pipeline": "Router → Quantitative Researcher → Empathy Copilot → Compliance Gatekeeper",
        }

    @router.post("/query")
    async def copilot_query(request: AdvisorQuery):
        """Submit a financial research query (B-end advisor).

        Returns the full AIResponse with market data, RAG context,
        compliance screening, and final narrative.
        """
        try:
            profile_dict = request.client_profile.to_dict() if request.client_profile else None
            result = await process_copilot_query(
                query=request.query,
                client_profile=profile_dict,
                conversation_id=request.conversation_id,
                metadata=request.metadata,
            )
            return result
        except Exception as exc:
            if HTTPException:
                raise HTTPException(status_code=500, detail=f"Agent pipeline error: {exc}") from exc
            raise


# ═══════════════════════════════════════════════════════════════
# Standalone handler (for Tornado server)
# ═══════════════════════════════════════════════════════════════

def get_copilot_status() -> Dict[str, str]:
    """Return copilot service metadata (used by Tornado handler)."""
    return {
        "service": "copilot",
        "status": "operational",
        "version": "0.3.0",
    }
