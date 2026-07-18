"""
SmartCycle — B-end Copilot Endpoints
AI-assisted advisory tools for financial professionals.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def copilot_root():
    """Placeholder — Copilot service entry point."""
    return {"service": "copilot", "status": "coming soon"}
