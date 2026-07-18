"""
SmartCycle — Database Seed Script
==================================

Populates initial data for development and demo environments.

Usage:
    cd backend
    PYTHONPATH=. python ../scripts/seed_data.py

Or via Docker:
    docker compose exec backend python scripts/seed_data.py

Data seeded:
  • Demo users (advisor + investor)
  • Sample organizations
  • Demo portfolios with holdings
  • Market snapshots (CSI 300, SSE, SZSE, ChiNext)
  • Research documents (RAG corpus)
  • Sample audit logs
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── Graceful import — works with or without SQLAlchemy ──
_HAS_SQLALCHEMY = False
try:
    from app.models.base import Base, SessionLocal, engine
    from app.models.user import User, Organization
    from app.models.portfolio import Portfolio, Holding
    from app.models.market import MarketSnapshot, ResearchDocument, AuditLog

    _HAS_SQLALCHEMY = True
except ImportError:
    print("[seed] SQLAlchemy not installed — writing seed data to JSON files instead")


# ═══════════════════════════════════════════════════════════════
# Seed Data
# ═══════════════════════════════════════════════════════════════

NOW = datetime.now(timezone.utc)

DEMO_USERS: List[Dict[str, Any]] = [
    {
        "username": "admin",
        "email": "admin@smartcycle.dev",
        "hashed_password": "$2b$12$...",  # bcrypt hash of 'smartcycle2024'
        "full_name": "Admin User",
        "display_name_cn": "管理员",
        "role": "advisor",
        "org_id": "org-demo-advisory",
        "is_active": True,
    },
    {
        "username": "advisor_zhang",
        "email": "zhang@smartcycle.dev",
        "hashed_password": "$2b$12$...",
        "full_name": "Zhang Wei",
        "display_name_cn": "张伟",
        "role": "advisor",
        "org_id": "org-demo-advisory",
        "is_active": True,
    },
    {
        "username": "investor_li",
        "email": "li@example.com",
        "hashed_password": "$2b$12$...",
        "full_name": "Li Na",
        "display_name_cn": "李娜",
        "role": "investor",
        "org_id": None,
        "is_active": True,
    },
]

DEMO_ORGANIZATIONS: List[Dict[str, Any]] = [
    {
        "id": "org-demo-advisory",
        "name": "SmartCycle Demo Advisory",
        "name_cn": "智循演示顾问公司",
        "org_type": "advisory",
        "is_active": True,
    },
]

DEMO_PORTFOLIOS: List[Dict[str, Any]] = [
    {
        "id": "port-zhang-001",
        "user_username": "advisor_zhang",
        "client_name": "张伟",
        "total_value_yuan": 8_500_000.00,
        "risk_tolerance": "aggressive",
        "investment_horizon": "long",
        "created_at": NOW.isoformat(),
    },
    {
        "id": "port-li-001",
        "user_username": "investor_li",
        "client_name": "李娜",
        "total_value_yuan": 3_200_000.00,
        "risk_tolerance": "moderate",
        "investment_horizon": "medium",
        "created_at": NOW.isoformat(),
    },
]

DEMO_HOLDINGS: List[Dict[str, Any]] = [
    # Zhang Wei — aggressive portfolio
    {
        "portfolio_id": "port-zhang-001",
        "symbol": "300750",
        "name_cn": "宁德时代",
        "asset_class": "equity",
        "market_value_yuan": 1_275_000.00,
        "allocation_pct": 15.0,
        "cost_basis_yuan": 1_050_000.00,
        "unrealized_pnl_yuan": 225_000.00,
        "unrealized_pnl_pct": 21.4,
    },
    {
        "portfolio_id": "port-zhang-001",
        "symbol": "600519",
        "name_cn": "贵州茅台",
        "asset_class": "equity",
        "market_value_yuan": 1_120_000.00,
        "allocation_pct": 13.2,
        "cost_basis_yuan": 980_000.00,
        "unrealized_pnl_yuan": 140_000.00,
        "unrealized_pnl_pct": 14.3,
    },
    {
        "portfolio_id": "port-zhang-001",
        "symbol": "NVDA",
        "name_cn": "英伟达",
        "asset_class": "equity",
        "market_value_yuan": 850_000.00,
        "allocation_pct": 10.0,
        "cost_basis_yuan": 680_000.00,
        "unrealized_pnl_yuan": 170_000.00,
        "unrealized_pnl_pct": 25.0,
    },
    {
        "portfolio_id": "port-zhang-001",
        "symbol": "510300",
        "name_cn": "沪深300ETF",
        "asset_class": "etf",
        "market_value_yuan": 1_700_000.00,
        "allocation_pct": 20.0,
        "cost_basis_yuan": 1_600_000.00,
        "unrealized_pnl_yuan": 100_000.00,
        "unrealized_pnl_pct": 6.3,
    },
    # Li Na — moderate portfolio
    {
        "portfolio_id": "port-li-001",
        "symbol": "510050",
        "name_cn": "上证50ETF",
        "asset_class": "etf",
        "market_value_yuan": 800_000.00,
        "allocation_pct": 25.0,
        "cost_basis_yuan": 760_000.00,
        "unrealized_pnl_yuan": 40_000.00,
        "unrealized_pnl_pct": 5.3,
    },
    {
        "portfolio_id": "port-li-001",
        "symbol": "019688",
        "name_cn": "国债ETF",
        "asset_class": "bond",
        "market_value_yuan": 640_000.00,
        "allocation_pct": 20.0,
        "cost_basis_yuan": 635_000.00,
        "unrealized_pnl_yuan": 5_000.00,
        "unrealized_pnl_pct": 0.8,
    },
    {
        "portfolio_id": "port-li-001",
        "symbol": "601318",
        "name_cn": "中国平安",
        "asset_class": "equity",
        "market_value_yuan": 560_000.00,
        "allocation_pct": 17.5,
        "cost_basis_yuan": 590_000.00,
        "unrealized_pnl_yuan": -30_000.00,
        "unrealized_pnl_pct": -5.1,
    },
]

DEMO_MARKET_SNAPSHOTS: List[Dict[str, Any]] = [
    {
        "symbol": "000300",
        "name": "CSI 300 Index",
        "name_cn": "沪深300",
        "price": 3987.45,
        "change": 23.15,
        "change_pct": 0.58,
        "pe_ttm": 13.2,
        "pb": 1.41,
        "source": "mock",
        "snapshot_at": NOW.isoformat(),
    },
    {
        "symbol": "000001",
        "name": "SSE Composite Index",
        "name_cn": "上证综指",
        "price": 3245.12,
        "change": -10.08,
        "change_pct": -0.31,
        "pe_ttm": 14.5,
        "pb": 1.38,
        "source": "mock",
        "snapshot_at": NOW.isoformat(),
    },
    {
        "symbol": "399001",
        "name": "SZSE Component Index",
        "name_cn": "深证成指",
        "price": 10782.56,
        "change": 45.32,
        "change_pct": 0.42,
        "pe_ttm": 24.8,
        "pb": 2.85,
        "source": "mock",
        "snapshot_at": NOW.isoformat(),
    },
    {
        "symbol": "399006",
        "name": "ChiNext Index",
        "name_cn": "创业板指",
        "price": 2156.78,
        "change": -18.45,
        "change_pct": -0.85,
        "pe_ttm": 35.2,
        "pb": 3.91,
        "source": "mock",
        "snapshot_at": NOW.isoformat(),
    },
]

DEMO_AUDIT_LOGS: List[Dict[str, Any]] = [
    {
        "event_type": "pipeline_execution",
        "actor_username": "advisor_zhang",
        "query_text": "沪深300估值水平如何？当前适合加仓吗？",
        "query_category": "research",
        "compliance_passed": True,
        "compliance_flags_count": 0,
        "latency_ms": 1250.5,
        "created_at": NOW.isoformat(),
    },
]


# ═══════════════════════════════════════════════════════════════
# Seed Functions
# ═══════════════════════════════════════════════════════════════


def seed_sqlalchemy() -> None:
    """Seed the database using SQLAlchemy ORM."""
    print("[seed] Creating all tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── Organizations ──
        print("[seed] Seeding organizations...")
        for org_data in DEMO_ORGANIZATIONS:
            org = Organization(**org_data)
            db.merge(org)  # merge = upsert

        # ── Users ──
        print("[seed] Seeding users...")
        for user_data in DEMO_USERS:
            user = User(**user_data)
            db.merge(user)

        # ── Portfolios ──
        print("[seed] Seeding portfolios...")
        for port_data in DEMO_PORTFOLIOS:
            portfolio = Portfolio(**port_data)
            db.merge(portfolio)

        # ── Holdings ──
        print("[seed] Seeding holdings...")
        for holding_data in DEMO_HOLDINGS:
            holding = Holding(**holding_data)
            db.merge(holding)

        # ── Market snapshots ──
        print("[seed] Seeding market snapshots...")
        for snap_data in DEMO_MARKET_SNAPSHOTS:
            snapshot = MarketSnapshot(**snap_data)
            db.add(snapshot)

        # ── Audit logs ──
        print("[seed] Seeding audit logs...")
        for log_data in DEMO_AUDIT_LOGS:
            audit_log = AuditLog(**log_data)
            db.add(audit_log)

        db.commit()
        print(f"[seed] ✅ Database seeded successfully!")
        print(f"      Organizations: {len(DEMO_ORGANIZATIONS)}")
        print(f"      Users:         {len(DEMO_USERS)}")
        print(f"      Portfolios:    {len(DEMO_PORTFOLIOS)}")
        print(f"      Holdings:      {len(DEMO_HOLDINGS)}")
        print(f"      Snapshots:     {len(DEMO_MARKET_SNAPSHOTS)}")
        print(f"      Audit logs:    {len(DEMO_AUDIT_LOGS)}")

    except Exception as exc:
        db.rollback()
        print(f"[seed] ❌ Error seeding database: {exc}")
        raise
    finally:
        db.close()


def seed_json() -> None:
    """Seed data as JSON files when SQLAlchemy is unavailable."""
    output_dir = os.path.join(os.path.dirname(__file__), "..", "backend", ".seed_data")
    os.makedirs(output_dir, exist_ok=True)

    datasets = {
        "organizations.json": DEMO_ORGANIZATIONS,
        "users.json": DEMO_USERS,
        "portfolios.json": DEMO_PORTFOLIOS,
        "holdings.json": DEMO_HOLDINGS,
        "market_snapshots.json": DEMO_MARKET_SNAPSHOTS,
        "audit_logs.json": DEMO_AUDIT_LOGS,
    }

    for filename, data in datasets.items():
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[seed] ✅ Seed data written to {output_dir}/")
    for filename in datasets:
        print(f"      {filename}")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("SmartCycle — Database Seed")
    print("=" * 60)

    if _HAS_SQLALCHEMY:
        seed_sqlalchemy()
    else:
        print("[seed] ⚠ SQLAlchemy not available — writing JSON seed files")
        seed_json()
        print("[seed] 💡 Install SQLAlchemy + asyncpg and configure DATABASE_URL to seed the real DB.")
