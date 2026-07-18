"""
SmartCycle — Market Data & Audit Models
=========================================

SQLAlchemy ORM models for market snapshots, research documents, and audit logging.

Python 3.9 compatible — uses typing.Optional/List, not PEP 604 syntax.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.base import _HAS_SQLALCHEMY

if _HAS_SQLALCHEMY:
    from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.orm import Mapped, mapped_column
    from app.models.base import Base, TimestampMixin, UUIDMixin


    class MarketSnapshot(Base, UUIDMixin):
        """Point-in-time market data snapshot for audit trail."""
        __tablename__ = "market_snapshots"

        symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
        name: Mapped[str] = mapped_column(String(200), nullable=False)
        name_cn: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
        sector: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
        price: Mapped[float] = mapped_column(Float, nullable=False)
        change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        change_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
        pe_ttm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        pb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        dividend_yield: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        market_cap_bn_cny: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        high_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        low_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        beta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        data_source: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
        snapshot_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

        def __repr__(self) -> str:
            return f"<MarketSnapshot {self.symbol} @ {self.price}>"


    class ResearchDocument(Base, UUIDMixin):
        """Financial research document indexed for RAG retrieval."""
        __tablename__ = "research_documents"

        title: Mapped[str] = mapped_column(String(500), nullable=False)
        source: Mapped[str] = mapped_column(String(200), nullable=False)
        date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        snippet: Mapped[str] = mapped_column(Text, nullable=False)
        keywords: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
        category: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
        embedding_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
        chunk_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
        total_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
        retrieval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
        last_retrieved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

        def __repr__(self) -> str:
            return f"<ResearchDoc {self.title[:50]}... [{self.category}]>"


    class AuditLog(Base, UUIDMixin, TimestampMixin):
        """Immutable audit trail for every AI agent decision."""
        __tablename__ = "audit_logs"

        user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
        conversation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
        query: Mapped[str] = mapped_column(Text, nullable=False)
        query_category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
        raw_data_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
        draft_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        final_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        disclaimer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        compliance_passed: Mapped[bool] = mapped_column(nullable=False)
        compliance_flags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
        revision_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
        latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
        llm_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
        data_source: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
        risk_tolerance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
        knowledge_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

        def __repr__(self) -> str:
            return f"<AuditLog {self.query_category} passed={self.compliance_passed} ({self.latency_ms}ms)>"

else:
    class MarketSnapshot:  # type: ignore[no-redef]
        """MarketSnapshot model stub (SQLAlchemy not installed)."""
        pass

    class ResearchDocument:  # type: ignore[no-redef]
        """ResearchDocument model stub (SQLAlchemy not installed)."""
        pass

    class AuditLog:  # type: ignore[no-redef]
        """AuditLog model stub (SQLAlchemy not installed)."""
        pass
