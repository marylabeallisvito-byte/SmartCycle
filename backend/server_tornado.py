"""
SmartCycle — Tornado API Server (Primary)
===========================================

Production API server using Tornado 6.5 (native async, Python 3.9 compatible).
Provides REST + WebSocket endpoints for the full SmartCycle platform.

Endpoints:
    # ── System ──
    GET  /api/v1/health              → health check
    GET  /api/v1/graph/info          → pipeline introspection

    # ── Core Pipeline ──
    POST /api/v1/chat                → full multi-agent pipeline

    # ── B-end Copilot ──
    GET  /api/v1/copilot             → copilot service status
    POST /api/v1/copilot/query       → advisor research query

    # ── C-end Companion ──
    GET  /api/v1/companion           → companion service status
    POST /api/v1/companion/chat      → retail investor chat

    # ── Compliance-as-a-Service ──
    GET  /api/v1/compliance           → compliance service status
    POST /api/v1/compliance/check     → standalone compliance screening
    GET  /api/v1/compliance/rules     → list active compliance rules

    # ── Market Data ──
    GET  /api/v1/market/summary       → major indices snapshot

    # ── Portfolio ──
    POST /api/v1/portfolio/analysis   → portfolio risk/return analytics

    # ── WebSocket ──
    WS   /ws/v1/chat                  → streaming chat

Usage:
    cd backend
    PYTHONPATH=. python -X utf8 server_tornado.py
    # → http://localhost:8000
"""

import html
import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import tornado.ioloop
import tornado.web
import tornado.websocket

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

# ═══════════════════════════════════════════════════════════════
# Rate Limiter — Token Bucket (per-IP)
# ═══════════════════════════════════════════════════════════════

class _TokenBucket:
    """Single token bucket for one client IP."""

    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate          # tokens per second
        self._burst = burst        # max tokens (bucket capacity)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def consume(self, count: int = 1) -> bool:
        self._refill()
        if self._tokens >= count:
            self._tokens -= count
            return True
        return False


class RateLimiter:
    """Per-IP token bucket rate limiter with configurable tiers.

    Default:  60 req/min (1.0 token/s, burst 10) — read endpoints.
    Strict:   10 req/min (0.167 token/s, burst 3) — LLM/chat endpoints.
    """

    def __init__(self) -> None:
        # (rate_per_sec, burst)
        self._default_tier: Tuple[float, int] = (1.0, 10)     # ~60/min
        self._strict_tier: Tuple[float, int] = (0.167, 3)     # ~10/min
        self._buckets: Dict[str, _TokenBucket] = {}
        # Cleanup stale entries every 1000 checks
        self._check_count: int = 0

    def _get_bucket(self, ip: str, tier: Tuple[float, int]) -> _TokenBucket:
        key = f"{ip}:{tier[0]:.3f}"
        if key not in self._buckets:
            self._buckets[key] = _TokenBucket(*tier)
        return self._buckets[key]

    def _maybe_cleanup(self) -> None:
        self._check_count += 1
        if self._check_count % 1000 == 0:
            now = time.monotonic()
            stale = [
                k for k, b in self._buckets.items()
                if now - b._last_refill > 600  # 10 min idle → evict
            ]
            for k in stale:
                del self._buckets[k]

    def check(self, ip: str, strict: bool = False) -> bool:
        """Return True if the request is within rate limits."""
        self._maybe_cleanup()
        tier = self._strict_tier if strict else self._default_tier
        bucket = self._get_bucket(ip, tier)
        return bucket.consume()

    def remaining(self, ip: str, strict: bool = False) -> int:
        tier = self._strict_tier if strict else self._default_tier
        bucket = self._get_bucket(ip, tier)
        bucket._refill()
        return max(0, int(bucket._tokens))


_rate_limiter = RateLimiter()

# ═══════════════════════════════════════════════════════════════
# Input Sanitization
# ═══════════════════════════════════════════════════════════════

# HTML tag pattern — strip all tags
_HTML_TAG_RE = re.compile(r"<[^>]*>", re.DOTALL)
# Control characters except common whitespace
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Sanitize user-provided text input.

    - Strip HTML tags
    - Remove control characters
    - Trim and enforce max length
    """
    if not isinstance(text, str):
        return ""
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def sanitize_dict_strings(obj: Any, max_length: int = 4000) -> Any:
    """Recursively sanitize all string values in a dict/list."""
    if isinstance(obj, str):
        return sanitize_text(obj, max_length)
    if isinstance(obj, dict):
        return {k: sanitize_dict_strings(v, max_length) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_dict_strings(item, max_length) for item in obj]
    return obj


# ═══════════════════════════════════════════════════════════════
# Base Handler with CORS
# ═══════════════════════════════════════════════════════════════

class BaseHandler(tornado.web.RequestHandler):
    """Base handler with CORS, rate limiting, and JSON helpers."""

    # Subclasses set this to True for endpoints that invoke the LLM pipeline
    _strict_rate_limit: bool = False

    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self) -> None:
        self.set_status(204)
        self.finish()

    def prepare(self) -> None:
        """Rate-limit check before every request."""
        client_ip = self.request.remote_ip or "127.0.0.1"
        if not _rate_limiter.check(client_ip, strict=self._strict_rate_limit):
            self.set_status(429)
            remaining = _rate_limiter.remaining(client_ip, strict=self._strict_rate_limit)
            self.set_header("Retry-After", "6")
            self.set_header("X-RateLimit-Remaining", str(remaining))
            self.write_json({
                "detail": "Too many requests. Please slow down and retry.",
                "retry_after_seconds": 6,
            })
            self.finish()
            return
        # Add rate-limit headers to response
        remaining = _rate_limiter.remaining(client_ip, strict=self._strict_rate_limit)
        self.set_header("X-RateLimit-Remaining", str(remaining))

    def write_json(self, data: Any) -> None:
        """Write a JSON response with proper content type."""
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(data)


# ═══════════════════════════════════════════════════════════════
# System Handlers
# ═══════════════════════════════════════════════════════════════

class HealthHandler(BaseHandler):
    """GET /api/v1/health"""

    def get(self) -> None:
        self.write_json({
            "status": "healthy",
            "version": "0.3.0",
            "phase": "Phase 6 — Full API surface + RAG pipeline",
            "endpoints": 14,
            "uptime_seconds": round(time.time() - _SERVER_START_TIME, 1),
        })


class GraphInfoHandler(BaseHandler):
    """GET /api/v1/graph/info"""

    def get(self) -> None:
        nodes = (
            list(smartcycle_graph.nodes.keys())
            if hasattr(smartcycle_graph, "nodes")
            else list(getattr(smartcycle_graph, "nodes", {}).keys())
        )
        self.write_json({
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


# ═══════════════════════════════════════════════════════════════
# Core Pipeline Handler
# ═══════════════════════════════════════════════════════════════

class ChatHandler(BaseHandler):
    """POST /api/v1/chat — triggers the full multi-agent pipeline."""

    _strict_rate_limit = True  # LLM endpoint

    async def post(self) -> None:
        t_start = time.perf_counter()

        # Parse request body
        try:
            body = json.loads(self.request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write_json({"detail": f"Invalid JSON: {exc}"})
            return

        # Input sanitization
        if "query" in body and isinstance(body["query"], str):
            body["query"] = sanitize_text(body["query"], max_length=4000)

        # Validate with Pydantic
        try:
            advisor_query = AdvisorQuery.model_validate(body)
        except Exception as exc:
            self.set_status(422)
            self.write_json({"detail": f"Validation error: {exc}"})
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
            self.write_json({"detail": f"Agent pipeline error: {exc}"})
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

        self.write_json(response.model_dump())


# ═══════════════════════════════════════════════════════════════
# B-end Copilot Handlers
# ═══════════════════════════════════════════════════════════════

class CopilotStatusHandler(BaseHandler):
    """GET /api/v1/copilot"""

    def get(self) -> None:
        self.write_json({
            "service": "copilot",
            "status": "operational",
            "version": "0.3.0",
            "pipeline": "Router → Quantitative Researcher → Empathy Copilot → Compliance Gatekeeper",
        })


class CopilotQueryHandler(BaseHandler):
    """POST /api/v1/copilot/query — B-end advisor query."""

    _strict_rate_limit = True  # LLM endpoint

    async def post(self) -> None:
        try:
            body = json.loads(self.request.body.decode("utf-8"))
            if "query" in body and isinstance(body["query"], str):
                body["query"] = sanitize_text(body["query"], max_length=4000)
            advisor_query = AdvisorQuery.model_validate(body)
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write_json({"detail": f"Invalid JSON: {exc}"})
            return
        except Exception as exc:
            self.set_status(422)
            self.write_json({"detail": f"Validation error: {exc}"})
            return

        t_start = time.perf_counter()

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

        try:
            final_state = await smartcycle_graph.ainvoke(initial_state)
        except Exception as exc:
            logger.exception("[copilot] Pipeline error")
            self.set_status(500)
            self.write_json({"detail": f"Agent pipeline error: {exc}"})
            return

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        compliance_flags: List[ComplianceFlag] = []
        for flag_dict in final_state.get("compliance_report", {}).get("flags", []):
            compliance_flags.append(ComplianceFlag(**flag_dict))

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

        logger.info("[copilot] category=%s latency=%.2fms", response.query_category, response.latency_ms)
        self.write_json(response.model_dump())


# ═══════════════════════════════════════════════════════════════
# C-end Companion Handlers
# ═══════════════════════════════════════════════════════════════

class CompanionStatusHandler(BaseHandler):
    """GET /api/v1/companion"""

    def get(self) -> None:
        self.write_json({
            "service": "companion",
            "status": "operational",
            "version": "0.3.0",
        })


class CompanionChatHandler(BaseHandler):
    """POST /api/v1/companion/chat — C-end retail investor chat."""

    _strict_rate_limit = True  # LLM endpoint

    async def post(self) -> None:
        try:
            body = json.loads(self.request.body.decode("utf-8"))
            if "query" in body and isinstance(body["query"], str):
                body["query"] = sanitize_text(body["query"], max_length=4000)
            advisor_query = AdvisorQuery.model_validate(body)
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write_json({"detail": f"Invalid JSON: {exc}"})
            return
        except Exception as exc:
            self.set_status(422)
            self.write_json({"detail": f"Validation error: {exc}"})
            return

        t_start = time.perf_counter()

        profile_dict: Optional[dict] = None
        if advisor_query.client_profile is not None:
            profile_dict = advisor_query.client_profile.to_dict()
        else:
            # Default retail investor profile
            profile_dict = {
                "risk_tolerance": "moderate",
                "anxiety_level": "medium",
                "investment_horizon": "medium",
                "knowledge_level": "beginner",
            }

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

        try:
            final_state = await smartcycle_graph.ainvoke(initial_state)
        except Exception as exc:
            logger.exception("[companion] Pipeline error")
            self.set_status(500)
            self.write_json({"detail": f"Agent pipeline error: {exc}"})
            return

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        compliance_flags: List[ComplianceFlag] = []
        for flag_dict in final_state.get("compliance_report", {}).get("flags", []):
            compliance_flags.append(ComplianceFlag(**flag_dict))

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

        logger.info("[companion] category=%s latency=%.2fms", response.query_category, response.latency_ms)
        self.write_json(response.model_dump())


# ═══════════════════════════════════════════════════════════════
# Compliance Handlers
# ═══════════════════════════════════════════════════════════════

class ComplianceStatusHandler(BaseHandler):
    """GET /api/v1/compliance"""

    def get(self) -> None:
        from app.agents import BANNED_PATTERNS
        self.write_json({
            "service": "compliance",
            "status": "operational",
            "version": "0.3.0",
            "active_rules_count": len(BANNED_PATTERNS),
        })


class ComplianceCheckHandler(BaseHandler):
    """POST /api/v1/compliance/check — standalone compliance screening."""

    def post(self) -> None:
        from app.agents import BANNED_PATTERNS, SUITABILITY_MAP
        import re

        try:
            body = json.loads(self.request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write_json({"detail": f"Invalid JSON: {exc}"})
            return

        text = body.get("text", "")
        risk_tolerance = body.get("risk_tolerance", "moderate")
        check_banned = body.get("check_banned_terms", True)
        check_suitability = body.get("check_suitability", True)

        # Sanitize input text
        text = sanitize_text(text, max_length=10000)

        if not text:
            self.set_status(422)
            self.write_json({"detail": "Field 'text' is required."})
            return

        flags: List[Dict[str, str]] = []

        # PASS 1: Banned terms
        if check_banned:
            for pattern, severity, suggestion in BANNED_PATTERNS:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    flags.append({
                        "rule": f"BANNED_TERM:{pattern}",
                        "severity": severity,
                        "banned_phrase": match.group(0),
                        "suggestion": suggestion,
                    })

        # PASS 2: Suitability
        if check_suitability and risk_tolerance in SUITABILITY_MAP:
            for term in SUITABILITY_MAP[risk_tolerance]:
                if term.lower() in text.lower():
                    flags.append({
                        "rule": f"SUITABILITY:{term}",
                        "severity": "medium",
                        "banned_phrase": term,
                        "suggestion": f"Term may be unsuitable for {risk_tolerance} investors.",
                    })

        has_critical = any(f["severity"] == "critical" for f in flags)
        has_high = any(f["severity"] == "high" for f in flags)

        if has_critical:
            passed, risk_rating = False, "high"
        elif has_high:
            passed, risk_rating = False, "medium"
        elif flags:
            passed, risk_rating = True, "low"
        else:
            passed, risk_rating = True, "clean"

        logger.info("[compliance] check: %d chars → passed=%s rating=%s flags=%d", len(text), passed, risk_rating, len(flags))

        self.write_json({
            "passed": passed,
            "flags_count": len(flags),
            "flags": flags,
            "risk_rating": risk_rating,
            "text_length": len(text),
            "checked_at": time.time(),
        })


class ComplianceRulesHandler(BaseHandler):
    """GET /api/v1/compliance/rules — list all active compliance rules."""

    def get(self) -> None:
        from app.agents import BANNED_PATTERNS, SUITABILITY_MAP, RISK_DISCLAIMER

        rules = []
        for pattern, severity, suggestion in BANNED_PATTERNS:
            rules.append({
                "pattern": pattern,
                "severity": severity,
                "suggestion": suggestion,
                "category": "banned_term",
            })

        for risk_level, terms in SUITABILITY_MAP.items():
            for term in terms:
                rules.append({
                    "pattern": term,
                    "severity": "medium",
                    "suggestion": f"Term may be unsuitable for {risk_level} investors.",
                    "category": "suitability",
                })

        self.write_json({
            "total_rules": len(rules),
            "rule_categories": ["banned_term", "suitability"],
            "rules": rules,
            "disclaimer": RISK_DISCLAIMER.strip(),
        })


# ═══════════════════════════════════════════════════════════════
# Auth Handlers
# ═══════════════════════════════════════════════════════════════

class AuthLoginHandler(BaseHandler):
    """POST /api/v1/auth/login — authenticate and receive JWT token.

    Uses a demo user for development (configured via env vars).
    In production, this would validate against the database.
    """

    def post(self) -> None:
        import os

        try:
            body = json.loads(self.request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write_json({"detail": f"Invalid JSON: {exc}"})
            return

        username = body.get("username", "")
        password = body.get("password", "")

        # Demo user authentication (env-configurable)
        demo_user = os.getenv("DEMO_USERNAME", "admin")
        demo_pass = os.getenv("DEMO_PASSWORD", "smartcycle2024")

        if username != demo_user or password != demo_pass:
            self.set_status(401)
            self.write_json({"detail": "Invalid username or password."})
            return

        # Generate JWT token
        from app.core.security import create_access_token
        from datetime import timedelta

        token_data = {
            "sub": username,
            "role": "advisor",
            "org_id": "demo-org",
        }
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=60),
        )

        logger.info("[auth] Login successful for user: %s", username)
        self.write_json({
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "username": username,
                "role": "advisor",
            },
        })


# ═══════════════════════════════════════════════════════════════
# Market & Portfolio Handlers
# ═══════════════════════════════════════════════════════════════

class MarketSummaryHandler(BaseHandler):
    """GET /api/v1/market/summary — major indices snapshot."""

    def get(self) -> None:
        from app.tools import fetch_market_data

        indices = []
        for symbol in ["000300", "000001", "399001", "399006"]:
            try:
                data = fetch_market_data(symbol)
                indices.append({
                    "symbol": symbol,
                    "name": data.get("name", ""),
                    "name_cn": data.get("name_cn", ""),
                    "price": data.get("price", 0),
                    "change": data.get("change", 0),
                    "change_pct": data.get("change_pct", 0),
                    "source": data.get("source", "mock"),
                })
            except Exception as exc:
                logger.warning("[market] Failed to fetch %s: %s", symbol, exc)
                indices.append({"symbol": symbol, "error": str(exc)})

        self.write_json({
            "indices": indices,
            "count": len(indices),
            "updated_at": time.time(),
        })


class PortfolioAnalysisHandler(BaseHandler):
    """POST /api/v1/portfolio/analysis — portfolio risk/return analytics."""

    def post(self) -> None:
        try:
            body = json.loads(self.request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.set_status(400)
            self.write_json({"detail": f"Invalid JSON: {exc}"})
            return

        holdings = body.get("holdings", [])
        total_value = body.get("total_value", 0.0)

        if not holdings:
            self.write_json({
                "total_value": total_value,
                "holdings_count": 0,
                "message": "No holdings provided for analysis.",
            })
            return

        # Basic portfolio analysis
        allocation: Dict[str, Dict[str, Any]] = {}
        for h in holdings:
            asset_class = h.get("asset_class", "other")
            if asset_class not in allocation:
                allocation[asset_class] = {"asset_class": asset_class, "value_yuan": 0.0, "count": 0}
            allocation[asset_class]["value_yuan"] += h.get("market_value_yuan", 0)
            allocation[asset_class]["count"] += 1

        total = sum(a["value_yuan"] for a in allocation.values())
        results = []
        for a in allocation.values():
            results.append({
                "asset_class": a["asset_class"],
                "value_yuan": round(a["value_yuan"], 2),
                "percentage": round(a["value_yuan"] / total * 100, 1) if total > 0 else 0,
                "count": a["count"],
            })

        # Concentration
        sorted_results = sorted(results, key=lambda x: x["percentage"], reverse=True)
        top_1_pct = sorted_results[0]["percentage"] if sorted_results else 0

        self.write_json({
            "total_value": round(total, 2),
            "holdings_count": len(holdings),
            "asset_classes_count": len(results),
            "allocation": sorted_results,
            "concentration": {
                "top_holding_pct": round(top_1_pct, 1),
                "diversified": top_1_pct < 50,
            },
        })


# ═══════════════════════════════════════════════════════════════
# WebSocket Handler — Streaming Chat
# ═══════════════════════════════════════════════════════════════

class ChatWebSocketHandler(tornado.websocket.WebSocketHandler):
    """WS /ws/v1/chat — streaming multi-agent pipeline via WebSocket.

    Sends JSON messages at each pipeline stage:
        {"stage": "router", "category": "research"}
        {"stage": "researcher", "ticker": "000300", "data_source": "mock"}
        {"stage": "copilot", "chunk": "关于沪深300..."}
        {"stage": "compliance", "passed": true, "flags": []}
        {"stage": "done", "final_response": "...", "latency_ms": 1200}
    """

    def check_origin(self, origin: str) -> bool:
        """Allow all origins for development."""
        return True

    def open(self) -> None:
        logger.info("[ws] Client connected")
        self.write_message(json.dumps({"stage": "connected", "message": "SmartCycle WebSocket ready"}))

    async def on_message(self, message: str) -> None:
        """Handle incoming chat message through the full pipeline with streaming."""
        t_start = time.perf_counter()

        try:
            body = json.loads(message)
            query_text = body.get("query", "")
            profile = body.get("client_profile", None)
        except json.JSONDecodeError:
            self.write_message(json.dumps({"stage": "error", "message": "Invalid JSON"}))
            return

        # Sanitize input
        query_text = sanitize_text(query_text, max_length=4000)

        if not query_text:
            self.write_message(json.dumps({"stage": "error", "message": "Missing 'query' field"}))
            return

        profile_dict: Optional[dict] = profile

        initial_state: AgentState = {
            "query": query_text,
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

        # ── Node 1: Router ──
        from app.agents import router_node
        partial = await router_node(initial_state)
        initial_state.update(partial)  # type: ignore[arg-type]
        self.write_message(json.dumps({
            "stage": "router",
            "category": initial_state.get("query_category", ""),
        }, ensure_ascii=False))

        # ── Node 2: Quantitative Researcher ──
        from app.agents import quantitative_researcher_node
        partial = await quantitative_researcher_node(initial_state)
        initial_state.update(partial)  # type: ignore[arg-type]
        raw = initial_state.get("raw_data", {})
        self.write_message(json.dumps({
            "stage": "researcher",
            "ticker": raw.get("extracted_ticker", ""),
            "data_source": raw.get("market_data", {}).get("source", "mock"),
            "rag_docs_count": len(raw.get("rag_context", [])),
        }, ensure_ascii=False))

        # ── Node 3 + 4: Copilot ⇄ Compliance loop ──
        from app.agents import empathy_copilot_node, compliance_gatekeeper_node, MAX_RETRIES
        from app.graph import _should_retry

        while True:
            partial = await empathy_copilot_node(initial_state)
            initial_state.update(partial)  # type: ignore[arg-type]
            draft = initial_state.get("draft_response", "")

            # Stream the draft in chunks
            chunk_size = 80
            for i in range(0, len(draft), chunk_size):
                self.write_message(json.dumps({
                    "stage": "copilot",
                    "chunk": draft[i:i + chunk_size],
                }, ensure_ascii=False))

            partial = await compliance_gatekeeper_node(initial_state)
            initial_state.update(partial)  # type: ignore[arg-type]

            passed = initial_state.get("compliance_passed", True)
            flags = initial_state.get("compliance_report", {}).get("flags", [])
            self.write_message(json.dumps({
                "stage": "compliance",
                "passed": passed,
                "flags_count": len(flags),
                "iteration": initial_state.get("iteration_count", 0),
            }, ensure_ascii=False))

            if not _should_retry(initial_state):
                break

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        self.write_message(json.dumps({
            "stage": "done",
            "final_response": initial_state.get("final_response", ""),
            "disclaimer": initial_state.get("disclaimer", ""),
            "compliance_passed": initial_state.get("compliance_passed", True),
            "latency_ms": latency_ms,
        }, ensure_ascii=False))

        logger.info("[ws] Pipeline complete: %s — %.2fms", initial_state.get("query_category", ""), latency_ms)

    def on_close(self) -> None:
        logger.info("[ws] Client disconnected")


# ═══════════════════════════════════════════════════════════════
# App Factory
# ═══════════════════════════════════════════════════════════════

_SERVER_START_TIME = time.time()


def make_app() -> tornado.web.Application:
    """Build the Tornado application with all routes."""
    return tornado.web.Application([
        # ── System ──
        # ── Auth ──
        (r"/api/v1/auth/login", AuthLoginHandler),

        # ── System ──
        (r"/api/v1/health", HealthHandler),
        (r"/api/v1/graph/info", GraphInfoHandler),

        # ── Core Pipeline ──
        (r"/api/v1/chat", ChatHandler),

        # ── B-end Copilot ──
        (r"/api/v1/copilot", CopilotStatusHandler),
        (r"/api/v1/copilot/query", CopilotQueryHandler),

        # ── C-end Companion ──
        (r"/api/v1/companion", CompanionStatusHandler),
        (r"/api/v1/companion/chat", CompanionChatHandler),

        # ── Compliance-as-a-Service ──
        (r"/api/v1/compliance", ComplianceStatusHandler),
        (r"/api/v1/compliance/check", ComplianceCheckHandler),
        (r"/api/v1/compliance/rules", ComplianceRulesHandler),

        # ── Market & Portfolio ──
        (r"/api/v1/market/summary", MarketSummaryHandler),
        (r"/api/v1/portfolio/analysis", PortfolioAnalysisHandler),

        # ── WebSocket ──
        (r"/ws/v1/chat", ChatWebSocketHandler),
    ])


# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SmartCycle (金仕达·智循) — Tornado API Server v0.3.0")
    logger.info("=" * 60)
    logger.info("REST Endpoints:")
    logger.info("  GET  /api/v1/health")
    logger.info("  GET  /api/v1/graph/info")
    logger.info("  POST /api/v1/chat")
    logger.info("  GET  /api/v1/copilot")
    logger.info("  POST /api/v1/copilot/query")
    logger.info("  GET  /api/v1/companion")
    logger.info("  POST /api/v1/companion/chat")
    logger.info("  GET  /api/v1/compliance")
    logger.info("  POST /api/v1/compliance/check")
    logger.info("  GET  /api/v1/compliance/rules")
    logger.info("  GET  /api/v1/market/summary")
    logger.info("  POST /api/v1/portfolio/analysis")
    logger.info("WebSocket:")
    logger.info("  WS   /ws/v1/chat")
    logger.info("=" * 60)
    logger.info("Starting on http://localhost:8000")
    app = make_app()
    app.listen(8000, address="127.0.0.1")
    tornado.ioloop.IOLoop.current().start()
