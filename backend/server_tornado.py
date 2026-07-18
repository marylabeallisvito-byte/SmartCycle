"""
SmartCycle — Tornado API Server (Network-Restricted Fallback)
=============================================================

Drop-in replacement for the FastAPI entrypoint when fastapi/uvicorn
cannot be installed. Uses Tornado (native async) + the existing agent pipeline.

Endpoints:
    GET  /api/v1/health      -> {"status": "healthy", "version": "0.2.0"}
    POST /api/v1/chat        -> AIResponse (full multi-agent pipeline)
    GET  /api/v1/graph/info  -> {"framework": "...", "pipeline": [...], "nodes": [...]}

Usage:
    cd backend
    python -X utf8 server_tornado.py
    # -> http://localhost:8000
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import tornado.ioloop
import tornado.web

from app.graph import smartcycle_graph
from app.schema import (
    AIResponse,
    AdvisorQuery,
    AgentState,
    ClientProfile,
    ComplianceFlag,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("smartcycle")


# ============================================================
# Handlers
# ============================================================

class HealthHandler(tornado.web.RequestHandler):
    """GET /api/v1/health"""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "*")
        self.set_header("Access-Control-Allow-Headers", "*")

    def get(self):
        self.write({
            "status": "healthy",
            "version": "0.2.0",
            "phase": "Phase 4 - Tornado fallback server",
        })

    def options(self):
        self.set_status(204)
        self.finish()


class GraphInfoHandler(tornado.web.RequestHandler):
    """GET /api/v1/graph/info"""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "*")
        self.set_header("Access-Control-Allow-Headers", "*")

    def get(self):
        nodes = (
            list(smartcycle_graph.nodes.keys())
            if hasattr(smartcycle_graph, "nodes")
            else list(getattr(smartcycle_graph, "nodes", {}).keys())
        )
        self.write({
            "framework": "LangGraph (fallback: _SimplePipeline)",
            "architecture": "FinRobot + tradingagents hybrid",
            "pipeline": [
                "Router (classification)",
                "Quantitative Researcher (tool-only, no LLM)",
                "Empathy Copilot (narrative generation)",
                "Compliance Gatekeeper (adversarial check + conditional loop-back)",
            ],
            "max_compliance_retries": 3,
            "nodes": nodes,
        })

    def options(self):
        self.set_status(204)
        self.finish()


class ChatHandler(tornado.web.RequestHandler):
    """POST /api/v1/chat - triggers the full multi-agent pipeline."""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "*")
        self.set_header("Access-Control-Allow-Headers", "*")

    async def post(self):
        t_start = time.perf_counter()

        # Parse request body
        try:
            body = json.loads(self.request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write({"detail": f"Invalid JSON: {exc}"})
            return

        # Validate with Pydantic
        try:
            advisor_query = AdvisorQuery.model_validate(body)
        except Exception as exc:
            self.set_status(422)
            self.write({"detail": f"Validation error: {exc}"})
            return

        # Build initial AgentState
        profile_dict: Optional[dict] = None
        if advisor_query.client_profile is not None:
            profile_dict = advisor_query.client_profile.to_dict()

        initial_state: AgentState = {
            "query": advisor_query.query,
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

        # Invoke the pipeline
        try:
            final_state = await smartcycle_graph.ainvoke(initial_state)
        except Exception as exc:
            logger.exception("Agent pipeline error")
            self.set_status(500)
            self.write({"detail": f"Agent pipeline error: {exc}"})
            return

        # Compute latency
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Build compliance flags
        compliance_flags: List[ComplianceFlag] = []
        for flag_dict in final_state.get("compliance_report", {}).get("flags", []):
            compliance_flags.append(ComplianceFlag(**flag_dict))

        # Build response
        response = AIResponse(
            query_category=final_state.get("query_category", ""),
            raw_data=final_state.get("raw_data", {}),
            draft_response=final_state.get("draft_response", ""),
            compliance_passed=bool(final_state.get("compliance_passed", True)),
            compliance_flags=compliance_flags,
            revision_count=final_state.get("iteration_count", 0),
            final_response=final_state.get("final_response", ""),
            disclaimer=final_state.get("disclaimer", ""),
            latency_ms=latency_ms,
            conversation_id=advisor_query.conversation_id,
        )

        logger.info(
            "[chat] category=%s latency=%.2fms compliance=%s flags=%d",
            response.query_category,
            response.latency_ms,
            response.compliance_passed,
            len(response.compliance_flags),
        )

        self.write(response.model_dump())

    def options(self):
        self.set_status(204)
        self.finish()


# ============================================================
# App factory
# ============================================================

def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        (r"/api/v1/health", HealthHandler),
        (r"/api/v1/graph/info", GraphInfoHandler),
        (r"/api/v1/chat", ChatHandler),
    ])


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    logger.info("Starting SmartCycle Tornado server on http://localhost:8000")
    app = make_app()
    app.listen(8000, address="127.0.0.1")
    tornado.ioloop.IOLoop.current().start()
