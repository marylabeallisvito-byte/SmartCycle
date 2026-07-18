"""
SmartCycle — RAG Pipeline Package
===================================

Hybrid retrieval pipeline for financial documents:
  • embeddings.py   — text → vector embedding (sentence-transformers or mock)
  • vector_store.py — in-memory / ChromaDB vector storage abstraction
  • retriever.py    — hybrid dense + sparse retrieval with score fusion

Usage:
    from app.rag import HybridRetriever
    retriever = HybridRetriever()
    results = retriever.retrieve("沪深300 估值", top_k=5)
"""

from app.rag.embeddings import EmbeddingProvider, MockEmbeddingProvider, get_embedding_provider
from app.rag.vector_store import VectorStore, get_vector_store
from app.rag.retriever import HybridRetriever, get_retriever

__all__ = [
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "get_embedding_provider",
    "VectorStore",
    "get_vector_store",
    "HybridRetriever",
    "get_retriever",
]
