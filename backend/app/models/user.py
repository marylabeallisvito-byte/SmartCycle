"""
SmartCycle — User & Organization Models
=========================================

SQLAlchemy ORM models for authentication and multi-tenancy.

When SQLAlchemy is installed: full ORM models with relationships.
When not installed: plain Python classes for documentation/reference.

Python 3.9 compatible — uses typing.Optional/List, not PEP 604 syntax.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from app.models.base import _HAS_SQLALCHEMY

if _HAS_SQLALCHEMY:
    from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
    from sqlalchemy.orm import Mapped, mapped_column, relationship
    from app.models.base import Base, TimestampMixin, UUIDMixin
    from app.models.portfolio import Portfolio  # type: ignore[misc]


    class Organization(Base, UUIDMixin, TimestampMixin):
        """Tenant organization for B-end (advisor firms)."""
        __tablename__ = "organizations"

        name: Mapped[str] = mapped_column(String(200), nullable=False)
        slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
        plan_tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
        max_advisors: Mapped[int] = mapped_column(Integer, default=5)
        max_clients: Mapped[int] = mapped_column(Integer, default=100)
        is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

        users: Mapped[List["User"]] = relationship("User", back_populates="organization", lazy="selectin")

        def __repr__(self) -> str:
            return f"<Organization {self.slug} ({self.plan_tier})>"


    class User(Base, UUIDMixin, TimestampMixin):
        """Platform user — advisor, investor, or admin."""
        __tablename__ = "users"
        __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

        email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
        hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
        full_name: Mapped[str] = mapped_column(String(200), nullable=False)
        display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
        role: Mapped[str] = mapped_column(String(20), default="investor", nullable=False, index=True)
        risk_tolerance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        investment_horizon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        knowledge_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
        org_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
        advisor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

        organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="users")
        portfolios: Mapped[List["Portfolio"]] = relationship("Portfolio", back_populates="user", lazy="selectin")

        def __repr__(self) -> str:
            return f"<User {self.email} ({self.role})>"

else:
    # SQLAlchemy not available — provide documentation-only stubs
    class Organization:  # type: ignore[no-redef]
        """Organization model stub (SQLAlchemy not installed)."""
        pass

    class User:  # type: ignore[no-redef]
        """User model stub (SQLAlchemy not installed)."""
        pass
