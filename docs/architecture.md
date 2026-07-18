# SmartCycle — Architecture Overview

> **Status**: Phase 1 — Scaffolding. This document will be updated as the system is built out.

## High-Level Design

SmartCycle follows a **modular monolith** pattern at the API layer, with clear domain boundaries enabling future extraction into microservices.

### Design Principles

1. **Compliance-First** — Every AI output passes through a compliance node before reaching the user.
2. **Multi-Agent by Default** — Complex financial reasoning is decomposed into specialized LangGraph nodes.
3. **RAG-Grounded** — All market insights are grounded in retrieved documents, not model hallucination.
4. **Streaming UX** — Server-Sent Events / WebSocket for real-time agent progress visibility.
5. **Auditability** — Every agent decision is logged with the input state, output, and compliance verdict.

### Agent Graph (LangGraph)

```
START → Market Analyst → Portfolio Advisor → Compliance Checker → END
          ↑                    ↑                    │
          │                    │                    ▼
          └── RAG Pipeline ───┘            (Reject & Re-route)
```

Each node is a Python async function that receives and returns `AgentState`. The graph supports:
- **Checkpointing** — Resume interrupted workflows
- **Human-in-the-Loop** — Pause for advisor approval on borderline compliance cases
- **Streaming** — Emit intermediate states to the frontend via WebSocket

### RAG Pipeline

1. **Ingestion**: Financial documents (PDFs, earnings transcripts, research reports) → text extraction → chunking.
2. **Embedding**: BGE-large-zh-v1.5 for Chinese-first, multilingual financial text.
3. **Storage**: ChromaDB collections partitioned by doc type (earnings, macro, regulatory).
4. **Retrieval**: Hybrid search — dense (semantic) + sparse (BM25 via pgvector) with re-ranking.
