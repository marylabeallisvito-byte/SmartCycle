"""
SmartCycle — SQLAlchemy Base & Mixins
=======================================

Provides the declarative base and common model mixins for the project.

When SQLAlchemy is installed: full ORM base with constraint conventions.
When not installed: plain Python stubs for documentation/reference.

Compatible with Python 3.9 — all annotations use typing module (no PEP 604).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Graceful degradation: models are defined but non-functional without SQLAlchemy
try:
    from sqlalchemy import DateTime, MetaData, func
    from sqlalchemy.dialects.postgresql import UUID as SA_UUID
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    _HAS_SQLALCHEMY = True
except ImportError:
    _HAS_SQLALCHEMY = False

# Naming convention for constraints — enables Alembic autogenerate
_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


if _HAS_SQLALCHEMY:

    class Base(DeclarativeBase):
        """SQLAlchemy declarative base with constraint naming conventions."""
        metadata = MetaData(naming_convention=_convention)


    class UUIDMixin:
        """Adds a UUID primary key column 'id'."""
        id: Mapped[uuid.UUID] = mapped_column(
            SA_UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )


    class TimestampMixin:
        """Adds 'created_at' and 'updated_at' timestamp columns."""
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            server_default=func.now(),
            nullable=False,
        )
        updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        )


    def model_to_dict(instance: Any, exclude: Optional[set] = None) -> Dict[str, Any]:
        """Convert a SQLAlchemy model instance to a plain dict."""
        exclude = exclude or set()
        result: Dict[str, Any] = {}
        for col in instance.__table__.columns:
            if col.name not in exclude:
                val = getattr(instance, col.name)
                if isinstance(val, datetime):
                    val = val.isoformat()
                elif isinstance(val, uuid.UUID):
                    val = str(val)
                result[col.name] = val
        return result

else:
    # SQLAlchemy not available — provide stub classes for documentation
    class Base:  # type: ignore[no-redef]
        """SQLAlchemy Base stub (SQLAlchemy not installed)."""
        pass

    class UUIDMixin:  # type: ignore[no-redef]
        """UUIDMixin stub (SQLAlchemy not installed)."""
        pass

    class TimestampMixin:  # type: ignore[no-redef]
        """TimestampMixin stub (SQLAlchemy not installed)."""
        pass

    def model_to_dict(instance: Any, exclude: Optional[set] = None) -> Dict[str, Any]:  # type: ignore[no-redef]
        """model_to_dict stub (SQLAlchemy not installed)."""
        return {}
