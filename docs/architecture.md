# SmartCycle — Architecture Overview

> **Status**: Phase 6 — Full API surface + RAG pipeline + Test suite (43 tests)
> **Last Updated**: 2026-07-18

## High-Level Design

SmartCycle follows a **modular monolith** pattern at the API layer, with clear domain boundaries enabling future extraction into microservices.

### Design Principles

1. **Compliance-First** — Every AI output passes through an adversarial Compliance Gatekeeper before reaching the user.
2. **Multi-Agent by Default** — Complex financial reasoning is decomposed into a 4-node LangGraph pipeline.
3. **RAG-Grounded** — All market insights are grounded in retrieved documents (HybridRetriever with dense + sparse fusion).
4. **Separation of Concerns** — Deterministic computation (tools) and LLM narrative generation reside in different nodes (FinRobot philosophy).
5. **Streaming UX** — WebSocket for real-time agent progress visibility.
6. **Auditability** — AuditLog model records pipeline traces for compliance replay.

### Agent Graph (LangGraph / _SimplePipeline)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         START                                        │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  Node 1: ROUTER         │ ← deterministic classifier
              │  data_fetching |         │   keyword matching, no LLM
              │  research | emotional    │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  Node 2: RESEARCHER     │ ← FinRobot: TOOLS ONLY
              │  fetch_market_data()    │   akshare/yfinance/mock
              │  hybrid_retrieve()      │   RAG pipeline
              │  web_search()           │   DuckDuckGo
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
         ┌────│  Node 3: COPILOT       │←──────────────┐
         │    │  Empathy + Narrative    │               │
         │    │  LLM (DeepSeek/Mock)    │               │
         │    └────────────┬────────────┘               │
         │                 │                             │
         │    ┌────────────▼────────────┐               │
         │    │  Node 4: COMPLIANCE     │               │
         │    │  PASS 0: User query     │               │
         │    │  PASS 1: Banned terms   │               │
         │    │  PASS 2: Suitability    │───────────────┘
         │    │  PASS 3: Disclaimer     │   retry (max 3x)
         │    └────────────┬────────────┘
         │                 │
         │           passed│
         │    ┌────────────▼────────────┐
         │    │         END              │
         │    └─────────────────────────┘

```

Each node is a Python async function receiving and returning `AgentState` (TypedDict). The graph supports:
- **Conditional edges** — Node 4 routes back to Node 3 on compliance failure.
- **Force-override** — After 3 retries, compliance hard-gate overrides output with a standardized risk disclaimer (tradingagents philosophy).
- **Streaming** — WebSocket at `/ws/v1/chat` emits JSON events at each pipeline stage.

### RAG Pipeline

```
Query → EmbeddingProvider (mock/SentenceTransformer) → VectorStore (JSON/ChromaDB)
     → HybridRetriever (dense 0.6 + sparse 0.4 fusion) → top-k docs
```

- **15-document financial corpus** covering: macro, regulation, sector, strategy, education, flow, industry, policy
- **Graceful degradation**: Falls back to legacy mock scorer if `app.rag` import fails

### Server Strategy

- **Tornado 6.5** (Primary): 13 REST + 1 WebSocket endpoint on `http://localhost:8000`
- **FastAPI** (Preserved): 3 original endpoints in `app/main.py` — retained for when `fastapi`/`uvicorn` become installable
