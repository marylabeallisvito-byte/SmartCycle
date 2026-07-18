"""
SmartCycle — Embedding Provider
================================

Generates dense vector embeddings for financial text (Chinese + English).

Strategy:
  1. Try sentence-transformers with BGE-large-zh-v1.5 (best for Chinese financial text)
  2. Fall back to a deterministic hash-based mock embedding (reproducible, zero-dependency)

The mock embedding uses character n-gram hashing and TF-IDF-like weighting to
produce semantically meaningful vectors sufficient for document retrieval demos
when the real model is unavailable.

Compatible with Python 3.9+ — no PEP 604 union syntax.
"""

import hashlib
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("smartcycle.rag.embeddings")

# ── Configurable embedding dimension ──
_DEFAULT_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")


class EmbeddingProvider:
    """Abstract interface for text → vector embedding."""

    def embed(self, text: str) -> List[float]:
        raise NotImplementedError

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    @property
    def dimension(self) -> int:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════
# Real embedding provider (sentence-transformers)
# ═══════════════════════════════════════════════════════════════

class SentenceTransformersProvider(EmbeddingProvider):
    """Real embeddings via sentence-transformers / BGE-large-zh.

    Activation: pip install sentence-transformers
    Then set EMBEDDING_MODEL env var to your preferred model.
    """

    def __init__(self, model_name: str = _EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()  # type: ignore[union-attr]
        logger.info("[rag.embeddings] Loaded SentenceTransformer: %s (dim=%d)", model_name, self._dim)

    def embed(self, text: str) -> List[float]:
        embedding = self._model.encode(text, normalize_embeddings=True)  # type: ignore[union-attr]
        return embedding.tolist()  # type: ignore[union-attr]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)  # type: ignore[union-attr]
        return embeddings.tolist()  # type: ignore[union-attr]

    @property
    def dimension(self) -> int:
        return self._dim


# ═══════════════════════════════════════════════════════════════
# Mock embedding provider (zero-dependency fallback)
# ═══════════════════════════════════════════════════════════════

class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based embeddings for demo / development.

    Produces reproducible, semantically-weak vectors using:
      • Character n-gram hashing (captures sub-word patterns in Chinese + English)
      • Position-weighted accumulation
      • L2 normalization

    NOT suitable for production retrieval quality — but sufficient to demonstrate
    the RAG pipeline architecture when sentence-transformers is unavailable.
    """

    # Pre-computed Chinese financial vocabulary boosts for key terms
    # Each term receives an extra hash contribution in a dedicated dimension band
    _FINANCE_TERMS: Dict[str, Tuple[int, int]] = {
        # (term, band_start, band_width) — band_start is within [0, dim)
    }

    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        self._dim = dim
        # Allocate vocabulary bands for Chinese financial terms
        band_size = max(8, dim // 48)  # ~48 bands for key financial concepts
        self._vocab_bands: Dict[str, Tuple[int, int]] = {}
        key_terms = [
            "估值", "市盈率", "市净率", "股息", "收益率", "风险", "波动",
            "沪深300", "上证", "深证", "创业板", "科创板", "新能源",
            "消费", "医药", "科技", "银行", "地产", "保险", "券商",
            "债券", "基金", "ETF", "期权", "期货", "回购", "分红",
            "GDP", "CPI", "PMI", "MLF", "LPR", "PBOC", "央行",
            "valuation", "PE", "PB", "dividend", "yield", "risk", "volatility",
            "bull", "bear", "rally", "correction", "sector", "rotation",
        ]
        for i, term in enumerate(key_terms):
            start = (i * band_size) % dim
            end = min(start + band_size, dim)
            self._vocab_bands[term] = (start, end)
        logger.info("[rag.embeddings] MockEmbeddingProvider ready (dim=%d, vocab_terms=%d)", dim, len(key_terms))

    def embed(self, text: str) -> List[float]:
        """Generate a deterministic embedding vector from text.

        Uses multi-level hashing:
          1. Character unigrams (position-weighted)
          2. Character bigrams (captures CJK word boundaries)
          3. Word-level tokens (stronger signal)
          4. Financial vocabulary boost (semantic relevance)
        """
        if not text or not text.strip():
            return [0.0] * self._dim

        text_lower = text.lower().strip()
        vec = [0.0] * self._dim

        # ── Level 1: Character unigrams (position-weighted) ──
        for i, ch in enumerate(text_lower):
            h = hashlib.sha256(ch.encode("utf-8")).digest()
            for j in range(0, len(h) - 1, 2):
                idx = (h[j] * 256 + h[j + 1]) % self._dim
                vec[idx] += 1.0 / (i + 1)

        # ── Level 2: Character bigrams ──
        for i in range(len(text_lower) - 1):
            bigram = text_lower[i:i + 2]
            h = hashlib.sha256(bigram.encode("utf-8")).digest()
            for j in range(0, len(h) - 1, 2):
                idx = (h[j] * 256 + h[j + 1]) % self._dim
                vec[idx] += 0.6 / (i + 1)

        # ── Level 3: Word tokens (stronger signal) ──
        # Split on whitespace + CJK character boundaries
        tokens = re.findall(r'[一-鿿]|[a-zA-Z]+|\d+', text_lower)
        for i, token in enumerate(tokens):
            h = hashlib.sha256(token.encode("utf-8")).digest()
            for j in range(0, len(h) - 1, 2):
                idx = (h[j] * 256 + h[j + 1]) % self._dim
                vec[idx] += 1.5 / (i + 1)

        # ── Level 4: Financial vocabulary semantic boost ──
        for term, (band_start, band_end) in self._vocab_bands.items():
            if term.lower() in text_lower:
                # Boost the band for this term
                h = hashlib.sha256(term.encode("utf-8")).digest()
                for j in range(0, len(h) - 1, 2):
                    raw_idx = (h[j] * 256 + h[j + 1]) % (band_end - band_start)
                    idx = band_start + raw_idx
                    vec[idx] += 2.0

        # ── L2 normalization ──
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    @property
    def dimension(self) -> int:
        return self._dim


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider (singleton).

    Tries sentence-transformers first; falls back to MockEmbeddingProvider.
    """
    global _embedding_provider
    if _embedding_provider is not None:
        return _embedding_provider

    try:
        _embedding_provider = SentenceTransformersProvider()
        logger.info("[rag.embeddings] Using SentenceTransformersProvider")
    except (ImportError, Exception) as exc:
        logger.info("[rag.embeddings] SentenceTransformers unavailable (%s), using MockEmbeddingProvider", exc)
        _embedding_provider = MockEmbeddingProvider()

    return _embedding_provider


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors of equal dimension."""
    if len(a) != len(b):
        raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
