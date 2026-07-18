# SmartCycle — API Specification

> **Base URL**: `http://localhost:8000/api/v1`
> **Server**: Tornado 6.5 (primary)
> **Last Updated**: 2026-07-18 (Phase 6)

## Current Endpoints (14 total)

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Service health check (version, phase, uptime) |
| GET | `/graph/info` | — | Pipeline introspection (nodes, architecture) |

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | — | JWT login (demo user: admin/smartcycle2024) |

### Core Pipeline

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | — | Full 4-node multi-agent pipeline |
| WS | `/ws/v1/chat` | — | Streaming pipeline via WebSocket |

### B-end Copilot

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/copilot` | — | Copilot service status |
| POST | `/copilot/query` | Optional JWT | Advisor research query (same pipeline as /chat) |

### C-end Companion

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/companion` | — | Companion service status |
| POST | `/companion/chat` | Optional JWT | Retail investor chat (default beginner profile) |

### Compliance-as-a-Service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/compliance` | — | Compliance service status + active rule count |
| POST | `/compliance/check` | — | Standalone compliance screening (banned terms + suitability) |
| GET | `/compliance/rules` | — | List all 27+ active compliance rules with suggestions |

### Market & Portfolio

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/market/summary` | — | CSI 300 + SSE + SZSE + ChiNext snapshot |
| POST | `/portfolio/analysis` | — | Portfolio risk/return analytics (allocation, concentration, diversification) |

---

## Request/Response Formats

### POST /chat (core pipeline)

**Request**:
```json
{
  "query": "沪深300估值水平如何？",
  "client_profile": {
    "risk_tolerance": "moderate",
    "anxiety_level": "medium",
    "investment_horizon": "medium",
    "knowledge_level": "intermediate"
  },
  "conversation_id": "conv-optional-123"
}
```

**Response**:
```json
{
  "query_category": "research",
  "raw_data": {
    "market_data": { "000300": { "price": 3987.45, "change_pct": 0.58, ... } },
    "rag_context": [ { "title": "...", "snippet": "...", "score": 0.85 } ],
    "web_context": [],
    "extracted_ticker": "000300"
  },
  "draft_response": "关于沪深300估值水平...",
  "compliance_passed": true,
  "compliance_flags": [],
  "revision_count": 0,
  "final_response": "关于沪深300估值水平...\n\n---\n⚠️ 风险提示...",
  "disclaimer": "...",
  "latency_ms": 1250.5,
  "timestamp": "2026-07-18T12:00:00Z",
  "conversation_id": "conv-optional-123"
}
```

### POST /auth/login

**Request**: `{ "username": "admin", "password": "smartcycle2024" }`

**Response**: `{ "access_token": "eyJ...", "token_type": "bearer", "user": { "username": "admin", "role": "advisor" } }`

### WS /ws/v1/chat

**Send**: `{ "query": "沪深300怎么样？", "client_profile": {...} }`

**Receive** (streaming JSON events):
```json
{"stage": "connected"}
{"stage": "router", "category": "research"}
{"stage": "researcher", "ticker": "000300", "data_source": "mock"}
{"stage": "copilot", "chunk": "关于沪深300..."}
{"stage": "compliance", "passed": true, "flags_count": 0}
{"stage": "done", "final_response": "...", "latency_ms": 1200}
```

---

## Planned Endpoints (Phase 7+)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/copilot/history` | Advisor query history (requires DB) |
| POST | `/copilot/portfolio/build` | Generate model portfolio |
| GET | `/companion/brief` | Daily AI market brief |
| POST | `/admin/users` | User management (admin only) |
| GET | `/admin/audit-logs` | Compliance audit trail |
