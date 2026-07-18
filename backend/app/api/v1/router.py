"""
SmartCycle — API v1 Router
Aggregates all endpoint routers under /api/v1.
"""

from fastapi import APIRouter

# TODO: Import and include sub-routers
# from app.api.v1.endpoints import copilot, companion, compliance

api_router = APIRouter(prefix="/api/v1")

# api_router.include_router(copilot.router, prefix="/copilot", tags=["B-end Copilot"])
# api_router.include_router(companion.router, prefix="/companion", tags=["C-end Companion"])
# api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])
