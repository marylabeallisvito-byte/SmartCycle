"""
SmartCycle — C-end Companion Endpoints
Empathetic, jargon-free market insights for retail investors.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def companion_root():
    """Placeholder — Companion service entry point."""
    return {"service": "companion", "status": "coming soon"}
