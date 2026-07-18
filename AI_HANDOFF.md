# SmartCycle (金仕达·智循) — AI Handoff Document

> **Generated**: 2026-07-18  
> **Last Session**: 2026-07-19 (Phase 8 — Mock DB expansion 6→49 + RAG corpus 15→30 + GitHub push)  
> **Current LLM**: DeepSeek `deepseek-chat` (API Key in backend/.env, NOT committed)  
> **Tests**: 43 backend + 15 frontend — all passing ✅  
> **TypeScript**: Zero compilation errors ✅  
> **Frontend**: http://localhost:3002 ✅ | **Backend**: http://localhost:8000 ✅

---

## 1. Project Overview

**SmartCycle (金仕达·智循)** — B2B2C financial intelligence & wealth management platform.

- **B-end**: Financial advisors — AI-assisted research, compliant client communication
- **C-end**: Retail investors — empathetic, jargon-free market insights

**Core Pipeline**: Router → Quantitative Researcher (tools only) → Empathy Copilot (LLM) → Compliance Gatekeeper (adversarial, conditional loop-back, max 3 retries)

**Tech Stack**:

| Layer | Technology | Status |
|---|---|---|
| Frontend | Next.js 15, TailwindCSS, ECharts, Three.js | ✅ |
| API Server | Tornado 6.5.5 (primary) | ✅ |
| LLM | DeepSeek `deepseek-chat` (OpenAI-compatible, httpx) | ✅ |
| Real-Time Data | akshare + yfinance → mock fallback | ✅ |
| Web Search | DuckDuckGo → empty-list fallback | ✅ |
| Agent Framework | `_SimplePipeline` (LangGraph preserved, not installed) | ✅ |
| RAG Pipeline | `app/rag/` — HybridRetriever + VectorStore + 15-doc corpus | ✅ |
| Vector Store | File-based JSON (ChromaDB-compatible interface) | ✅ |
| Database | PostgreSQL + pgvector (models defined, DB pending) | ⚠ |
| WebSocket | `/ws/v1/chat` — streaming pipeline events | ✅ |
| Auth | JWT pure stdlib (no jose/passlib/pydantic_settings) | ✅ |
| Rate Limiting | Token bucket per-IP (60/min default, 10/min strict) | ✅ |
| Input Sanitization | HTML strip + control char removal | ✅ |
| Error Boundary | React ErrorBoundary with reset-key remount | ✅ |
| Cancel/Timeout | AbortController wired to axios, 90s timeout | ✅ |
| Pipeline Progress | 4-node visual indicator in ChatInterface | ✅ |
| WebSocket Reconnect | Exponential backoff + heartbeat in `createReconnectingWebSocket()` | ✅ |
| Accessibility | ARIA roles, labels, live regions on ChatInterface + page | ✅ |
| WebGL Fallback | Static fallback card in Client3DProfile | ✅ |
| Tests | 43 backend + 15 frontend, standalone runners | ✅ |

---

## 2. Architecture

### 2.1 The 4-Node Pipeline

```
START
  │
  ▼
┌──────────────────────────┐
│ Node 1: ROUTER           │  ← deterministic keyword classifier, NO LLM
│ → data_fetching          │
│ → research               │
│ → emotional_support      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Node 2: QUANT RESEARCHER │  ← FinRobot: TOOLS ONLY, NO LLM
│ • fetch_market_data()    │     akshare/yfinance → mock fallback
│ • hybrid_retrieve()      │     RAG pipeline → legacy scorer fallback
│ • web_search_async()     │     DuckDuckGo (httpx.AsyncClient) → empty-list fallback
│ • _extract_ticker()      │     general regex (A-share 6-digit + US ticker 1-6 letters)
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Node 3: EMPATHY COPILOT  │←──────────────┐
│ • _real_llm_generate()   │               │ retry (max 3x)
│   → DeepSeek (primary)   │               │ with revision_notes
│   → _mock_llm_generate() │               │
│ • Tone calibration       │               │
│ • Risk-aware framing     │               │
└──────────┬───────────────┘               │
           │                                │
           ▼                                │
┌──────────────────────────┐               │
│ Node 4: COMPLIANCE GATE  │               │
│ PASS 0: scan USER query  │               │
│ PASS 1: banned-term scan │───────────────┘
│ PASS 2: suitability check│
│ PASS 3: attach disclaimer │  ← get_risk_disclaimer() (fresh timestamp each call)
│ Force-override on max retries (tradingagents hard gate)
└──────────┬───────────────┘
           │ (passed or force-override)
           ▼
          END
```

### 2.2 Design Principles

- **FinRobot**: Separation of Computation (Node 2) vs Narrative (Node 3). `raw_data` is the sole bridge.
- **tradingagents**: Adversarial compliance with conditional loop-back (max 3 retries from `COMPLIANCE_MAX_RETRIES` env). Force-override after exhaustion.
- **OpenBB**: Structured data fetching — flat dicts of facts only, no prose.
- **FinRAG**: Hybrid dense + sparse retrieval with 0.6/0.4 weighted fusion.

---

## 3. Complete File Inventory

### 3.1 Backend (`backend/`) — Key Files

| File | Key Contents |
|---|---|
| `server_tornado.py` | PRIMARY server — 14 endpoints + WebSocket + rate limiter + sanitization |
| `app/agents.py` | 4 async nodes + `get_risk_disclaimer()` + `BANNED_PATTERNS` (27 rules) + `SUITABILITY_MAP` + `_extract_ticker()` (general regex) |
| `app/graph.py` | `_build_langgraph_graph()` + `_SimplePipeline` fallback (with logging) |
| `app/llm.py` | `OpenAILikeLLM` (httpx async) + `MockLLM` + `_load_env_file()` |
| `app/tools.py` | `fetch_market_data()` + `hybrid_retrieve()` + `web_search()` / `web_search_async()` + `_MOCK_MARKET_DB` (6 entries: 600519, NVDA, 000300, 000001, 399001, 399006) |
| `app/schema.py` | Pydantic V2 models + AgentState TypedDict + 5 enums |
| `app/core/config.py` | Pure stdlib config (no pydantic-settings) |
| `app/core/security.py` | Pure stdlib JWT (hmac+hashlib) + PBKDF2 password hash |
| `app/rag/embeddings.py` | `MockEmbeddingProvider` (384-dim) + `SentenceTransformersProvider` (ready) |
| `app/rag/vector_store.py` | File-based JSON VectorStore; `get_vector_store()` with `reset` option |
| `app/rag/retriever.py` | `HybridRetriever` — 15-doc corpus, dense+sparse fusion, WRRF |
| `app/services/market_data.py` | `MarketDataService` — instance-level cache, `asyncio.get_running_loop()` |
| `app/services/llm_service.py` | `LLMService` — `generate(raise_on_error=True)` for retry propagation |
| `app/services/portfolio.py` | `PortfolioService` — HHI, diversification, Sharpe (annotated as estimate) |
| `app/models/` | 8 SQLAlchemy ORM models (auto-degrade to stubs) |
| `tests/` | 43 tests — schema (12), compliance (14), agents (17) + standalone runner |

### 3.2 Frontend (`frontend/`) — Key Files

| File | Key Contents |
|---|---|
| `src/app/page.tsx` | Master dashboard — search filter, dynamic AUM, MarketTicker, empty state, nav with disabled states |
| `src/components/ChatInterface.tsx` | Chat + cancel + PipelineProgressIndicator + Compliance Shield + auto-expand textarea + ARIA |
| `src/components/Client3DProfile.tsx` | Three.js + `checkWebGLSupport()` static fallback |
| `src/components/MarketTicker.tsx` | Real-time scrolling index ticker, 60s auto-refresh |
| `src/components/charts/AssetAllocationChart.tsx` | ECharts sunburst/donut + empty state |
| `src/lib/api.ts` | 16 typed API functions + auth interceptor + `createReconnectingWebSocket()` |
| `src/lib/useChat.ts` | API-wired hook with AbortController + progress + timeout |
| `src/lib/mockData.ts` | 4 mock clients + allocations; re-exports types from `@/types` |
| `src/types/index.ts` | Canonical TS types: `ChatMessage`, `AgentTrace`, `AIResponse`, etc. |

### 3.3 Docs & CI

| File | Description |
|---|---|
| `.github/workflows/ci.yml` | ruff + mypy + standalone tests + vitest + build |
| `docs/architecture.md` | 4-node graph diagram, RAG pipeline, server strategy |
| `docs/api-spec.md` | 14 endpoints with request/response examples |
| `scripts/seed_data.py` | Full implementation — 6 datasets (ready to run) |

---

## 4. Phase 7.5 Changes (2026-07-19 Session)

### 4.1 Priority 1 — Critical Bug Fixes (6/6)

| # | File | Fix |
|---|---|---|
| 1 | `agents.py` | `RISK_DISCLAIMER` → `get_risk_disclaimer()` function (fresh timestamp per call) |
| 2 | `tools.py` | Sync `web_search()` → new `web_search_async()` with `httpx.AsyncClient`; agent nodes use async version |
| 3 | `services/llm_service.py` | `generate()` adds `raise_on_error` param; `generate_with_retry()` passes `True` so exceptions reach retry loop |
| 4 | `services/portfolio.py` | Sharpe ratio annotated as rough estimate; recommends historical return series for production |
| 5 | `tools.py` | `_REAL_DATA_TIMEOUT` correctly used in timeout params |
| 6 | `agents.py` | All 3 tool `.invoke()` calls in `quantitative_researcher_node` wrapped in try/except |

### 4.2 Priority 2 — Medium Fixes (8/8)

| # | File | Fix |
|---|---|---|
| 7 | `graph.py` | `except (ImportError, Exception)` split into separate handlers; `logger.warning()` on compile failure |
| 8 | `rag/vector_store.py` | `get_vector_store()` validates `persist_dir` consistency; `reset=True` to force recreation |
| 9 | `agents.py` | `_extract_ticker()` uses general regex `[A-Z]{1,6}` + common-word filter (replaced 6 hardcoded tickers) |
| 10 | `tools.py` | `_fetch_real_csi_index()` tries `stock_zh_index_spot_em()` first, falls back to daily |
| 11 | `services/market_data.py` | `asyncio.get_event_loop()` → `asyncio.get_running_loop()` |
| 12 | `services/market_data.py` | Module-level `_cache` → instance attribute `self._cache` |
| 13 | `tools.py` | Unknown tickers return `{"status": "error"}` with clear message — NO fabricated data |
| 14 | `frontend/src/lib/api.ts` | `createReconnectingWebSocket()` with exponential backoff + heartbeat |

### 4.3 Priority 3 — Frontend & Polish (10/10)

| # | File | Fix |
|---|---|---|
| 15 | `types/index.ts` + `mockData.ts` | `ChatMessage` + `AgentTrace` unified in `types/index.ts`; `mockData.ts` re-exports |
| 16 | `mockData.ts` | `MOCK_AGENT_TRACE` preserved with demo-purpose comment |
| 17 | `page.tsx` | Non-active nav buttons have `disabled` + `title` tooltip ("Coming in Phase 8") |
| 18 | `ChatInterface.tsx` | Textarea auto-expands via `onInput` handler (max 120px) |
| 19 | `AssetAllocationChart.tsx` | Empty `allocations` renders placeholder ("暂无资产配置数据") |
| 20 | `useChat.ts` | Added comment explaining how to wire progress to real WebSocket events |
| 21 | `Client3DProfile.tsx` | `checkWebGLSupport()` + static profile card fallback |
| 22 | `README.md` | Removed non-existent `/docs` reference (Tornado has no Swagger UI) |
| 23 | `ChatInterface.tsx` + `page.tsx` | Added `role="log"`, `aria-live="polite"`, `aria-label` on buttons and inputs |
| 24 | `agents.py` | `MAX_RETRIES` reads from `os.getenv("COMPLIANCE_MAX_RETRIES", "3")` |

### 4.4 Mock DB Expansion

| File | Change |
|---|---|
| `tools.py` `_MOCK_MARKET_DB` | Expanded from 3 to **6 entries**: added `000001` (上证综指), `399001` (深证成指), `399006` (创业板指) |

### 4.5 Test Updates

- `tests/test_compliance.py`: `RISK_DISCLAIMER` → `get_risk_disclaimer()` import
- Backend: 43/43 passing ✅
- Frontend: 15/15 passing ✅
- TypeScript: zero errors ✅

---

## 5. Key Architectural Decisions & Gotchas

### 5.1 Python 3.9 Compatibility (CRITICAL)
- ❌ No `X | Y` union syntax → use `Optional[X]`, `Dict[K,V]`, `List[X]`
- ❌ No `from __future__ import annotations` in files with Pydantic `BaseModel`

### 5.2 Graceful Degradation Matrix

| Component | With Dependencies | Without Dependencies |
|---|---|---|
| LLM generation | DeepSeek real-time API | `_mock_llm_generate()` template-based |
| A-share data | akshare (EastMoney) | `_MOCK_MARKET_DB` (6 entries: 3 stocks + 3 indices) |
| US stock data | yfinance | Mock DB (NVDA only) |
| RAG retrieval | `HybridRetriever` (real embeddings) | Legacy `_MOCK_DOCUMENTS` + `_dense_score`/`_sparse_score` |
| Embeddings | SentenceTransformers (BGE-large-zh) | `MockEmbeddingProvider` (hash-based 384-dim) |
| Web search | DuckDuckGo (httpx.AsyncClient) | Empty list |
| JWT | python-jose (optional) | Pure stdlib `hmac` + `hashlib` |
| Password hash | passlib (optional) | Pure stdlib `PBKDF2-SHA256` |
| Database models | Full SQLAlchemy ORM | Plain Python stubs |

### 5.3 LangGraph NOT Installed
`langgraph` and `langchain_core` are NOT available. Pipeline uses `_SimplePipeline`. `_build_langgraph_graph()` is preserved — activates automatically when langgraph becomes installable.

### 5.4 Network Constraints

| Resource | Status | Note |
|---|---|---|
| DeepSeek API | ✅ Reachable | `trust_env=False` bypasses system proxy |
| akshare / yfinance / DuckDuckGo | ❌ Proxy-blocked | Auto-fallback to mock |
| pip install | ❌ SSL/proxy errors | Zero additional dependencies needed |

### 5.5 New Key Functions to Know

- **`get_risk_disclaimer()`** (`agents.py`) — NOT a constant; call it each time for fresh compliance timestamp
- **`web_search_async()`** (`tools.py`) — use in async contexts; `web_search()` still available for sync
- **`createReconnectingWebSocket()`** (`frontend/src/lib/api.ts`) — preferred over raw `createChatWebSocket()`
- **`generate(raise_on_error=True)`** (`services/llm_service.py`) — use in retry loops so exceptions propagate
- **`get_vector_store(reset=True)`** (`rag/vector_store.py`) — force new singleton with different `persist_dir`

### 5.6 Dual Server Strategy
- **Tornado** (`server_tornado.py`): **PRIMARY** — all 14 endpoints. No Swagger `/docs`.
- **FastAPI** (`app/main.py`): **PRESERVED** — 3 original endpoints. Has Swagger `/docs`.

---

## 6. How to Run

### Prerequisites
- Python 3.9+ (3.9 verified)
- Node.js 22+
- DeepSeek API key (already in `backend/.env`)

### Start Backend
```bash
cd backend
PYTHONPATH=. python -X utf8 server_tornado.py
# → http://localhost:8000 (14 endpoints)
```

### Start Frontend
```bash
cd frontend
npm install --legacy-peer-deps    # Required: @react-three/fiber v9 vs drei peer conflict
npm run dev
# → http://localhost:3000 (or :3001, :3002 if ports occupied)
```

### Run Tests
```bash
# Backend (43 tests)
cd backend && PYTHONPATH=. python tests/run_tests.py

# Frontend (15 tests)
cd frontend && npx vitest run

# TypeScript check
cd frontend && npx tsc --noEmit
```

---

## 7. Full API Surface (14 endpoints)

| Method | Endpoint | Rate Limit | Description |
|---|---|---|---|
| GET | `/api/v1/health` | Default | Health check (version, phase, uptime, endpoints=14) |
| POST | `/api/v1/auth/login` | Default | JWT login (demo: admin/smartcycle2024) |
| POST | `/api/v1/chat` | **Strict** | Full 4-node multi-agent pipeline |
| GET | `/api/v1/graph/info` | Default | Pipeline introspection |
| GET | `/api/v1/copilot` | Default | B-end copilot service status |
| POST | `/api/v1/copilot/query` | **Strict** | B-end advisor research query |
| GET | `/api/v1/companion` | Default | C-end companion service status |
| POST | `/api/v1/companion/chat` | **Strict** | C-end retail investor chat |
| GET | `/api/v1/compliance` | Default | Compliance service status + rule count |
| POST | `/api/v1/compliance/check` | Default | Standalone compliance screening |
| GET | `/api/v1/compliance/rules` | Default | Full list of 27+ active rules |
| GET | `/api/v1/market/summary` | Default | CSI 300 + SSE + SZSE + ChiNext snapshot |
| POST | `/api/v1/portfolio/analysis` | Default | Risk/return analytics |
| WS | `/ws/v1/chat` | — | Streaming pipeline stage updates |

---

## 8. Remaining Work (Phase 8+)

| # | Priority | Task | Key Files |
|---|---|---|---|
| 1 | 🔴 | **Database wiring** — Install SQLAlchemy + asyncpg, run alembic, wire DB sessions | `server_tornado.py`, `app/models/`, `app/core/config.py`, `scripts/seed_data.py` |
| 2 | 🟡 | **RAG production upgrade** — `pip install chromadb sentence-transformers`, swap mock embedder + JSON store | `app/rag/embeddings.py`, `app/rag/vector_store.py` |
| 3 | 🟡 | **Real-time LLM token streaming** — Current WebSocket streams pipeline stages, not LLM tokens | `server_tornado.py` ChatWebSocketHandler, `app/llm.py` |
| 4 | 🟡 | **Configuration centralization** — `app/llm.py` and `app/core/config.py` read env vars independently; unify into single source of truth | `app/llm.py`, `app/core/config.py` |
| 5 | 🔵 | **C-end standalone UI** — Lightweight retail investor interface separate from advisor dashboard | `frontend/src/app/` new route |
| 6 | 🔵 | **DuckDuckGo → Financial news API** — Replace with EastMoney/Sina/Bloomberg API | `app/tools.py` `web_search_async()` |
| 7 | 🔵 | **Pipeline progress via WebSocket** — Replace simulated setTimeout progress with real server events | `useChat.ts`, `server_tornado.py` |
| 8 | 🔵 | **E2E tests** — Playwright/Cypress for critical user flows | `tests/` |

---

## 9. Quick Reference: Key Files to Modify

### Compliance rules
→ `backend/app/agents.py` — `BANNED_PATTERNS` (27 patterns: 9 EN + 18 CN), `SUITABILITY_MAP`, `get_risk_disclaimer()`, `MAX_RETRIES` (env-configurable)

### Mock market data
→ `backend/app/tools.py` — `_MOCK_MARKET_DB` (6 entries: 600519, NVDA, 000300, 000001, 399001, 399006)

### RAG documents
→ `backend/app/rag/retriever.py` — `_DEFAULT_DOCUMENTS` (15 docs, indexed on first `get_retriever()` call)

### Database wiring
→ `backend/server_tornado.py` — add DB session management per request
→ `backend/app/models/` — models fully defined, auto-degrade to stubs
→ `backend/app/core/config.py` — `DATABASE_URL` already configured
→ `scripts/seed_data.py` — seed script fully implemented, ready to run

### RAG production upgrade
→ `backend/app/rag/embeddings.py` — `SentenceTransformersProvider` class already written, just needs `pip install sentence-transformers`
→ `backend/app/rag/vector_store.py` — swap `persist_dir` to ChromaDB `PersistentClient`

### DeepSeek API key
→ `backend/.env` — `LLM_API_KEY` already configured; update `LLM_BASE_URL`, `LLM_MODEL` as needed

### Frontend types
→ `frontend/src/types/index.ts` — canonical TypeScript types (single source of truth)
→ `frontend/src/lib/mockData.ts` — re-exports types from `@/types`

### WebSocket
→ `frontend/src/lib/api.ts` — `createReconnectingWebSocket()` for resilient connections
→ `frontend/src/lib/useChat.ts` — progress simulation (see §8 #7 for WebSocket wiring)

---

## 10. Environment State

| Item | Detail |
|---|---|
| **Python** | 3.9 with tornado 6.5.5, pydantic 2.13.4, httpx 0.28.1, akshare, yfinance, cryptography |
| **Node.js** | 22 with npm (640 packages, `--legacy-peer-deps`) |
| **DeepSeek API** | ✅ Reachable (`trust_env=False`) |
| **pip install** | ❌ SSL/proxy errors |
| **akshare / yfinance / DuckDuckGo** | ❌ Proxy-blocked → automatic mock fallback |
| **NOT installed** | fastapi, uvicorn, langgraph, langchain_core, chromadb, sqlalchemy, asyncpg, pytest, pytest-cov, sentence-transformers, jose, passlib, bcrypt, pydantic_settings |
| **Vitest** | ✅ v2.1.9 in node_modules |
| **Git** | ✅ `C:\Users\S\Desktop\金仕达比赛\` |

---

## 11. Phase 8 Changes (2026-07-19 Later Session)

### 11.1 Mock Market DB Expansion (6 → 49 entries)

**File:** `backend/app/tools.py` — `_MOCK_MARKET_DB`

| Category | Before | After | Examples |
|---|---|---|---|
| A-Shares (10+ sectors) | 1 (Moutai) | **26** | 五粮液, CATL, BYD, LONGi, SMIC, NAURA, CMB, Ping An, Mindray, iFLYTEK |
| US Stocks | 1 (NVDA) | **8** | AAPL, MSFT, TSLA, GOOGL, AMZN, META, JPM |
| Indices | 4 | **6** | +SSE 50 (000016), +CSI 500 (000905) |
| ETFs | 0 | **5** | 510300, 510050, 510500, 588000, 159915 |
| Convertible Bonds | 0 | **2** | 113053 (隆22转债), 110079 (平银转债) |

Sectors covered: Baijiu, New Energy/Battery/Solar, Semiconductor, Banking, Insurance, Healthcare/Pharma/Medical Devices/TCM, AI/Tech/Fintech, Auto, Defense, Real Estate, Mining, Utilities, Telecom.

### 11.2 RAG Corpus Expansion (15 → 30 documents)

**File:** `backend/app/rag/retriever.py` — `_DEFAULT_DOCUMENTS`

15 new documents: DeepSeek AI impact, healthcare/aging, baijiu/consumer, gold/commodities, STAR Market, Fed/global macro, digital yuan, portfolio risk management, US stocks, convertible bonds, banking NIM, market microstructure, defense sector, technical analysis, ETF ecosystem.

Categories: macro (4), regulation (2), sector (8), strategy (6), education (5), flow (1), industry (3), policy (1).

### 11.3 Legacy RAG Fallback (6 → 20 docs) + .gitignore Updates

**Files:** `backend/app/tools.py` — `_MOCK_DOCUMENTS`, `.gitignore`, `.env.example`

- `_MOCK_DOCUMENTS`: 6 → 20 docs matching retriever.py categories
- `.gitignore`: added `.chroma_mock/` exclusion
- `.env.example`: added `COMPLIANCE_MAX_RETRIES=3`

### 11.4 Security Audit

- ✅ Verified `backend/.env` gitignored and NOT in git history
- ✅ No API keys hardcoded in any source file
- ✅ `.env.example` uses placeholder values only

---

## 12. Session Summary

```
Phase 8 (2026-07-19 Later) — MVP Hardening
├── Mock DB: 6 → 49 entries                    ✅  (10+ sectors, 5 asset classes)
├── RAG corpus: 15 → 30 documents              ✅  (8 categories)
├── Legacy RAG fallback: 6 → 20 docs           ✅
├── Security audit: no leaked keys             ✅
├── .gitignore + .env.example updated          ✅
├── Tests: all pass                            ✅  (43 BE + 15 FE)
└── TypeScript: zero errors                    ✅

Phase 7.5 (2026-07-19) — Quality Polish
├── Priority 1: 6 critical bugs fixed           ✅
├── Priority 2: 8 medium issues fixed           ✅
├── Priority 3: 10 frontend/polish fixes        ✅
├── Hotfix: _MOCK_MARKET_DB expanded            ✅  (3 → 6 entries)
├── Tests: all pass                             ✅  (43 BE + 15 FE)
├── TypeScript: zero errors                     ✅
└── Pending: 8 Phase 9+ enhancements            📋

Total: 28 issues resolved across 2 sessions.
```

<p align="center">
  <strong>End of Handoff Document</strong><br/>
  <sub>SmartCycle (金仕达·智循) · Phase 8 Complete · 58 Tests Pass · 14 Endpoints · 49 Mock Tickers · 30 RAG Docs</sub><br/>
  <sub>DeepSeek API Secure · No Hardcoded Keys · ARIA Accessibility · WebSocket Reconnect</sub>
</p>
