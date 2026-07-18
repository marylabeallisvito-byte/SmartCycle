# SmartCycle — API Specification

> **Base URL**: `http://localhost:8000/api/v1`
> **OpenAPI Docs**: `http://localhost:8000/docs`

## Endpoints (Planned)

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Service health check |

### B-end Copilot

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/copilot/query` | JWT | Submit a research/portfolio query |
| GET | `/copilot/history` | JWT | Query history for an advisor |
| POST | `/copilot/portfolio/build` | JWT | Generate model portfolio |

### C-end Companion

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/companion/chat` | JWT | Streaming chat for retail investors |
| GET | `/companion/brief` | JWT | Daily AI market brief |

### Compliance

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/compliance/check` | JWT | Validate text against rules |
| GET | `/compliance/rules` | JWT | List active compliance rules |

### Market Data

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/market/summary` | — | AI-generated daily market summary |
| GET | `/market/indices` | — | Real-time index data |
