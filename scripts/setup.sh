#!/usr/bin/env bash
# ============================================================
# SmartCycle — Development Setup Script
# ============================================================
set -euo pipefail

echo "🚀 SmartCycle (金仕达·智循) — Environment Setup"
echo "================================================"

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ node required"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "⚠️  docker not found — Docker Compose will not work"; }

# Backend
echo ""
echo "📦 Setting up Python backend..."
cd backend
python3 -m venv .venv 2>/dev/null || echo "   (venv already exists)"
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   ✅ Backend dependencies installed"
cd ..

# Frontend
echo ""
echo "📦 Setting up Next.js frontend..."
cd frontend
npm install --silent
echo "   ✅ Frontend dependencies installed"
cd ..

# Environment file
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env created from .env.example — please edit it with your keys!"
fi

echo ""
echo "================================================"
echo "✅ Setup complete!"
echo ""
echo "  Start with Docker:   docker compose up --build"
echo "  Or run locally:      cd backend && uvicorn app.main:app --reload"
echo "                       cd frontend && npm run dev"
echo "================================================"
