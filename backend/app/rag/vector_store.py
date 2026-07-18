"""
SmartCycle — Vector Store Abstraction
======================================

File-based JSON vector store for development and demo.
Swap to ChromaDB in production by implementing the same interface.

Design:
  • Each document is stored as a JSON file: {id}.json
  • Contains: id, text, metadata, embedding
  • Search: brute-force cosine similarity (OK for <10K documents)
  • Persistence: automatic write on add/delete

Python 3.9 compatible — no PEP 604 union syntax.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("smartcycle.rag.vector_store")


def _l2_normalize(vec: List[float]) -> List[float]:
    """L2-normalize a vector in-place (returns new list)."""
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec[:]
    return [v / norm for v in vec]


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore:
    """File-based vector store with JSON persistence.

    Stores documents as individual JSON files in a directory.
    Search performs brute-force cosine similarity over all documents.

    Swap to ChromaDB in production:
        import chromadb
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection("docs")
    """

    def __init__(self, persist_dir: str = ".chroma_mock") -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._index: List[Dict[str, Any]] = []
        self._load_all()
        logger.info("[rag.vector_store] Initialized at %s (%d documents)", self._persist_dir, len(self._index))

    # ── Public API ──────────────────────────────────────────

    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add documents to the vector store.

        Args:
            documents: List of document texts.
            embeddings: List of embedding vectors (same length as documents).
            metadatas: Optional list of metadata dicts.
            ids: Optional list of document IDs (auto-generated if None).

        Returns:
            List of document IDs that were added.
        """
        if len(documents) != len(embeddings):
            raise ValueError(f"documents ({len(documents)}) and embeddings ({len(embeddings)}) must have same length")

        if ids is None:
            ids = [f"doc_{int(time.time() * 1_000_000)}_{i}" for i in range(len(documents))]
        if metadatas is None:
            metadatas = [{} for _ in documents]

        added_ids = []
        for doc_id, text, emb, meta in zip(ids, documents, embeddings, metadatas):
            entry = {
                "id": doc_id,
                "text": text,
                "embedding": emb,
                "metadata": meta,
                "created_at": time.time(),
            }
            # Persist to disk
            file_path = self._persist_dir / f"{doc_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            # Add to in-memory index
            self._index.append(entry)
            added_ids.append(doc_id)

        logger.info("[rag.vector_store] Added %d documents (total: %d)", len(added_ids), len(self._index))
        return added_ids

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for documents most similar to the query embedding.

        Args:
            query_embedding: The query vector.
            top_k: Number of results to return.

        Returns:
            List of dicts with keys: id, text, metadata, score.
        """
        if not self._index:
            return []

        # Normalize query embedding
        q_vec = _l2_normalize(query_embedding)

        # Compute scores for all documents
        scored = []
        for doc in self._index:
            doc_vec = _l2_normalize(doc["embedding"])
            score = _cosine_sim(q_vec, doc_vec)
            scored.append((score, doc))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top_k results
        results = []
        for score, doc in scored[:top_k]:
            results.append({
                "id": doc["id"],
                "text": doc["text"],
                "metadata": doc.get("metadata", {}),
                "score": round(score, 4),
            })

        return results

    def delete(self, ids: List[str]) -> int:
        """Delete documents by ID. Returns count of deleted docs."""
        deleted = 0
        for doc_id in ids:
            file_path = self._persist_dir / f"{doc_id}.json"
            if file_path.exists():
                file_path.unlink()
                deleted += 1
        # Rebuild index
        self._index = [d for d in self._index if d["id"] not in set(ids)]
        logger.info("[rag.vector_store] Deleted %d documents (remaining: %d)", deleted, len(self._index))
        return deleted

    def count(self) -> int:
        """Return the number of indexed documents."""
        return len(self._index)

    def clear(self) -> None:
        """Remove all documents from the store."""
        for doc in self._index:
            file_path = self._persist_dir / f"{doc['id']}.json"
            if file_path.exists():
                file_path.unlink()
        self._index = []
        logger.info("[rag.vector_store] Cleared all documents")

    # ── Internal ────────────────────────────────────────────

    def _load_all(self) -> None:
        """Load all persisted documents into the in-memory index."""
        self._index = []
        if not self._persist_dir.exists():
            return
        for file_path in self._persist_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    self._index.append(doc)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("[rag.vector_store] Skipping corrupt file %s: %s", file_path.name, exc)


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

_store: Optional[VectorStore] = None


def get_vector_store(persist_dir: str = ".chroma_mock", reset: bool = False) -> VectorStore:
    """Return the singleton VectorStore instance.

    Args:
        persist_dir: Directory for vector store persistence. Only used on
                     first call or when reset=True. If the directory differs
                     from the existing singleton's directory, a warning is
                     logged and the existing instance is returned unchanged
                     (unless reset=True).
        reset: If True, discard the existing singleton and create a new one
               with the given persist_dir.
    """
    global _store
    if _store is not None:
        if reset:
            logger.info("[rag.vector_store] Resetting singleton with persist_dir=%s", persist_dir)
            _store = VectorStore(persist_dir=persist_dir)
        elif str(_store._persist_dir) != str(persist_dir) and str(_store._persist_dir) != str(Path(persist_dir)):
            logger.warning(
                "[rag.vector_store] persist_dir mismatch: requested '%s' but singleton already at '%s'. "
                "Use reset=True to force recreation.",
                persist_dir, _store._persist_dir
            )
        return _store
    _store = VectorStore(persist_dir=persist_dir)
    return _store
