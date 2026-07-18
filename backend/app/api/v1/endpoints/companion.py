"""
SmartCycle — C-end Companion Endpoints
=======================================

Empathetic, jargon-free market insights for retail investors.

POST /api/v1/companion/chat
    Chat with the AI companion — calibrated for retail investors with
    simplified language, empathy, and risk-aware responses.
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

async def process_companion_chat(
    query: str,
    client_profile: Optional[dict] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Process a C-end investor chat query through the agent pipeline.

    C-end queries differ from B-end:
      - Beginner-friendly default profile
      - Simplified responses with less jargon
      - Higher empathy modulation
      - Mandatory risk disclaimers at appropriate reading level
    """
    t_start = time.perf_counter()

    # Default retail investor profile if none provided
    if client_profile is None:
        client_profile = {
            "risk_tolerance": "moderate",
            "anxiety_level": "medium",
            "investment_horizon": "medium",
            "knowledge_level": "beginner",
        }

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
    async def companion_root():
        """Companion service status."""
        return {
            "service": "companion",
            "status": "operational",
            "version": "0.3.0",
            "pipeline": "Router → Quantitative Researcher → Empathy Copilot → Compliance Gatekeeper",
        }

    @router.post("/chat")
    async def companion_chat(request: AdvisorQuery):
        """Chat with the AI investment companion (C-end retail investor).

        Calibrated for retail investors with simplified language,
        empathy, and risk-aware responses.
        """
        try:
            profile_dict = request.client_profile.to_dict() if request.client_profile else None
            result = await process_companion_chat(
                query=request.query,
                client_profile=profile_dict,
                conversation_id=request.conversation_id,
            )
            return result
        except Exception as exc:
            if HTTPException:
                raise HTTPException(status_code=500, detail=f"Agent pipeline error: {exc}") from exc
            raise


# ═══════════════════════════════════════════════════════════════
# Standalone handler (for Tornado server)
# ═══════════════════════════════════════════════════════════════

def get_companion_status() -> Dict[str, str]:
    """Return companion service metadata (used by Tornado handler)."""
    return {
        "service": "companion",
        "status": "operational",
        "version": "0.3.0",
    }
