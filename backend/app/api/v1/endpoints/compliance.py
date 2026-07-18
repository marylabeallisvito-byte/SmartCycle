"""
SmartCycle — Compliance-as-a-Service Endpoints
Automated regulatory checks for financial communications.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def compliance_root():
    """Placeholder — Compliance service entry point."""
    return {"service": "compliance", "status": "coming soon"}
