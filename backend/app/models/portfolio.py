"""
SmartCycle — Portfolio & Holdings Models
==========================================

SQLAlchemy ORM models for investment portfolios and their holdings.

Python 3.9 compatible — uses typing.Optional/List, not PEP 604 syntax.
"""

import uuid
from typing import List, Optional

from app.models.base import _HAS_SQLALCHEMY

if _HAS_SQLALCHEMY:
    from sqlalchemy import Boolean, Float, ForeignKey, String, Text
    from sqlalchemy.orm import Mapped, mapped_column, relationship
    from app.models.base import Base, TimestampMixin, UUIDMixin
    from app.models.user import User  # type: ignore[misc]


    class Portfolio(Base, UUIDMixin, TimestampMixin):
        """An investment portfolio belonging to a user."""
        __tablename__ = "portfolios"

        user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        name: Mapped[str] = mapped_column(String(200), nullable=False)
        description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        total_value_yuan: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
        currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
        risk_tolerance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        benchmark_symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        ytd_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        one_year_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

        user: Mapped["User"] = relationship("User", back_populates="portfolios")
        holdings: Mapped[List["Holding"]] = relationship("Holding", back_populates="portfolio", lazy="selectin", cascade="all, delete-orphan")

        def __repr__(self) -> str:
            return f"<Portfolio {self.name} (¥{self.total_value_yuan:,.0f})>"


    class Holding(Base, UUIDMixin, TimestampMixin):
        """A single asset holding within a portfolio."""
        __tablename__ = "holdings"

        portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
        symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
        name: Mapped[str] = mapped_column(String(200), nullable=False)
        asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
        market: Mapped[str] = mapped_column(String(10), nullable=False)
        quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
        avg_cost_yuan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        current_price_yuan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        market_value_yuan: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
        allocation_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
        unrealized_pnl_yuan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        unrealized_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        beta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        annual_volatility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

        portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")

        def __repr__(self) -> str:
            return f"<Holding {self.symbol} ({self.asset_class}) ¥{self.market_value_yuan:,.0f}>"

else:
    class Portfolio:  # type: ignore[no-redef]
        """Portfolio model stub (SQLAlchemy not installed)."""
        pass

    class Holding:  # type: ignore[no-redef]
        """Holding model stub (SQLAlchemy not installed)."""
        pass
