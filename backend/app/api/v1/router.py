"""
SmartCycle — API v1 Router
============================

Aggregates all endpoint routers under /api/v1.

Note: This router uses FastAPI conventions. When FastAPI is not installed,
the Tornado server (server_tornado.py) provides equivalent endpoints directly.
"""

try:
    from fastapi import APIRouter

    from app.api.v1.endpoints import copilot, companion, compliance

    api_router = APIRouter(prefix="/api/v1")

    api_router.include_router(copilot.router, prefix="/copilot", tags=["B-end Copilot"])
    api_router.include_router(companion.router, prefix="/companion", tags=["C-end Companion"])
    api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])

except ImportError:
    # FastAPI not installed — router is not used (Tornado handles all endpoints)
    api_router = None  # type: ignore[assignment]
