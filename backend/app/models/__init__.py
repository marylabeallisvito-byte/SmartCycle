"""
SmartCycle — SQLAlchemy ORM Models
====================================

Import all models here so Alembic autogenerate can discover them.

When SQLAlchemy is installed, all models are available.
When not installed (e.g., offline dev), models gracefully degrade to stubs.

Usage:
    from app.models import Base, User, Organization, Portfolio, Holding
    from app.models import MarketSnapshot, ResearchDocument, AuditLog
"""

from app.models.base import _HAS_SQLALCHEMY

if _HAS_SQLALCHEMY:
    from app.models.base import Base, UUIDMixin, TimestampMixin, model_to_dict
    from app.models.user import User, Organization
    from app.models.portfolio import Portfolio, Holding
    from app.models.market import MarketSnapshot, ResearchDocument, AuditLog
else:
    # SQLAlchemy not installed — provide documentation stubs
    Base = None  # type: ignore[assignment]
    UUIDMixin = None  # type: ignore[assignment]
    TimestampMixin = None  # type: ignore[assignment]

    def model_to_dict(*args, **kwargs):  # type: ignore[no-redef]
        return {}

    User = None  # type: ignore[assignment]
    Organization = None  # type: ignore[assignment]
    Portfolio = None  # type: ignore[assignment]
    Holding = None  # type: ignore[assignment]
    MarketSnapshot = None  # type: ignore[assignment]
    ResearchDocument = None  # type: ignore[assignment]
    AuditLog = None  # type: ignore[assignment]

__all__ = [
    "_HAS_SQLALCHEMY",
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "model_to_dict",
    "User",
    "Organization",
    "Portfolio",
    "Holding",
    "MarketSnapshot",
    "ResearchDocument",
    "AuditLog",
]
