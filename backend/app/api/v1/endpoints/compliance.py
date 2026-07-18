"""
SmartCycle — Compliance-as-a-Service Endpoints
================================================

Standalone compliance screening for financial communications.

POST /api/v1/compliance/check
    Validate any text against regulatory rules.
    Returns compliance verdict, flags, and suggested rewrites.
    This is the core "Compliance-as-a-Service" API.

GET /api/v1/compliance/rules
    List active compliance rules with severity levels.
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.agents import BANNED_PATTERNS, SUITABILITY_MAP, RISK_DISCLAIMER

# FastAPI router (only used when fastapi is installed)
try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field
    router = APIRouter()
    _HAS_FASTAPI = True
except ImportError:
    APIRouter = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    router = None  # type: ignore[assignment]
    _HAS_FASTAPI = False


# ═══════════════════════════════════════════════════════════════
# Pydantic Schemas (for standalone compliance API)
# ═══════════════════════════════════════════════════════════════

class ComplianceCheckRequest:
    """Request for standalone compliance screening.

    Not a Pydantic BaseModel to avoid import issues when pydantic is unavailable.
    """
    def __init__(
        self,
        text: str,
        risk_tolerance: str = "moderate",
        check_banned_terms: bool = True,
        check_suitability: bool = True,
    ) -> None:
        self.text = text
        self.risk_tolerance = risk_tolerance
        self.check_banned_terms = check_banned_terms
        self.check_suitability = check_suitability


# Try to make it a proper Pydantic model if available
try:
    from pydantic import BaseModel as _BaseModel, Field as _Field

    class ComplianceCheckRequest(_BaseModel):
        """Standalone compliance check request."""
        text: str = _Field(..., min_length=1, max_length=10_000, description="Text to screen for compliance.")
        risk_tolerance: str = _Field(default="moderate", description="Risk tolerance for suitability check.")
        check_banned_terms: bool = _Field(default=True, description="Run banned-term regex scan.")
        check_suitability: bool = _Field(default=True, description="Run suitability check.")

except ImportError:
    pass  # Use the plain class above


# ═══════════════════════════════════════════════════════════════
# Core Logic
# ═══════════════════════════════════════════════════════════════

def check_compliance(
    text: str,
    risk_tolerance: str = "moderate",
    check_banned_terms: bool = True,
    check_suitability: bool = True,
) -> Dict[str, Any]:
    """Standalone compliance screening.

    Runs the same checks as the Compliance Gatekeeper agent node
    but as an independent, callable service.

    Args:
        text: The text to screen.
        risk_tolerance: conservative | moderate | aggressive
        check_banned_terms: Run PASS 1 (banned-term regex scan).
        check_suitability: Run PASS 2 (suitability check).

    Returns:
        Dict with passed, flags, modified_text, and risk_rating.
    """
    flags: List[Dict[str, str]] = []
    modified_text = text

    # ── PASS 1: Banned-term scan ──
    if check_banned_terms:
        for pattern, severity, suggestion in BANNED_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                flags.append({
                    "rule": f"BANNED_TERM:{pattern}",
                    "severity": severity,
                    "banned_phrase": match.group(0),
                    "suggestion": suggestion,
                })

    # ── PASS 2: Suitability check ──
    if check_suitability:
        risk_level = risk_tolerance.lower()
        if risk_level in SUITABILITY_MAP:
            flagged_terms = SUITABILITY_MAP[risk_level]
            for term in flagged_terms:
                if term.lower() in text.lower():
                    flags.append({
                        "rule": f"SUITABILITY:{term}",
                        "severity": "medium",
                        "banned_phrase": term,
                        "suggestion": f"Term '{term}' may be unsuitable for {risk_tolerance} investors. "
                                       "Consider softer language or adding a risk caveat.",
                    })

    # ── Determine verdict ──
    has_critical = any(f["severity"] == "critical" for f in flags)
    has_high = any(f["severity"] == "high" for f in flags)

    if has_critical:
        passed = False
        risk_rating = "high"
    elif has_high:
        passed = False
        risk_rating = "medium"
    elif flags:
        passed = True  # low severity only — pass with warnings
        risk_rating = "low"
    else:
        passed = True
        risk_rating = "clean"

    return {
        "passed": passed,
        "flags_count": len(flags),
        "flags": flags,
        "risk_rating": risk_rating,
        "text_length": len(text),
        "disclaimer_appended": not passed,
        "checked_at": time.time(),
    }


def get_active_rules() -> Dict[str, Any]:
    """Return all active compliance rules for transparency.

    This allows frontends to display what rules are being enforced.
    """
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

    return {
        "total_rules": len(rules),
        "rule_categories": ["banned_term", "suitability"],
        "rules": rules,
        "disclaimer": RISK_DISCLAIMER.strip(),
    }


# ═══════════════════════════════════════════════════════════════
# FastAPI Endpoints
# ═══════════════════════════════════════════════════════════════

if _HAS_FASTAPI:

    @router.get("/")
    async def compliance_root():
        """Compliance service status."""
        return {
            "service": "compliance",
            "status": "operational",
            "version": "0.3.0",
            "active_rules_count": len(BANNED_PATTERNS),
        }

    @router.post("/check")
    async def compliance_check(request: ComplianceCheckRequest):
        """Screen text against regulatory compliance rules.

        This is the standalone Compliance-as-a-Service endpoint.
        Use it to validate any financial communication before it reaches a client.
        """
        try:
            result = check_compliance(
                text=request.text,
                risk_tolerance=request.risk_tolerance,
                check_banned_terms=request.check_banned_terms,
                check_suitability=request.check_suitability,
            )
            return result
        except Exception as exc:
            if HTTPException:
                raise HTTPException(status_code=500, detail=f"Compliance check error: {exc}") from exc
            raise

    @router.get("/rules")
    async def compliance_rules():
        """List all active compliance rules."""
        return get_active_rules()
