"""
SmartCycle — Tool Layer (Real-Time Data + Fallback)
====================================================

Architectural synthesis:
  • OpenBB-style  → structured, deterministic market-data fetching
  • FinRAG-style  → hybrid dense + sparse document retrieval

DESIGN PRINCIPLE (FinRobot philosophy):
  ─────────────────────────────────────
  These tools return RAW, STRUCTURED DATA only.
  They do NOT generate narrative, advice, or prose.
  The Quantitative Researcher agent CALLS these tools and
  populates AgentState.raw_data BEFORE any LLM is invoked.

  This enforces the strict separation:
    Tool output (deterministic)  ←→  LLM narrative (generative)

Each tool exposes a .invoke(dict) method compatible with LangChain's
@tool convention.  When langchain_core is installed, the _tool decorator
delegates to the real @tool; otherwise it uses a transparent passthrough.

DATA SOURCE STRATEGY (Phase 5):
  • A-shares (6-digit codes) → akshare (real-time, free)
  • US stocks (letter tickers) → yfinance (real-time, free)
  • Indexes (CSI 300, SSE, etc.) → akshare
  • Fallback → hardcoded _MOCK_MARKET_DB (when network unavailable)
"""

import asyncio
import logging
import os
import random
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("smartcycle.tools")

# ── Graceful degradation: use real @tool if available, else no-op ──
try:
    from langchain_core.tools import tool as _langchain_tool
    _tool = _langchain_tool
except ImportError:
    # Standalone mode — wrap the function with a .invoke() method
    def _tool(func: Callable) -> Callable:
        """Passthrough decorator: adds .invoke(kwargs) for LangChain compatibility."""
        def _invoke(kwargs: dict) -> Any:
            return func(**kwargs)
        func.invoke = _invoke  # type: ignore[attr-defined]
        return func

# ═══════════════════════════════════════════════════════════════
# Deterministic seed — ensures reproducible mock outputs
# ═══════════════════════════════════════════════════════════════
_SEED = 42
_rng = random.Random(_SEED)

# ═══════════════════════════════════════════════════════════════
# Real-time market data fetchers (Phase 5)
# ═══════════════════════════════════════════════════════════════

# ── Network timeout for data fetches ──
_REAL_DATA_TIMEOUT = float(os.getenv("MARKET_DATA_TIMEOUT", "8.0"))


def _is_a_share(symbol: str) -> bool:
    """Check if symbol looks like an A-share code (6 digits starting with 0/3/6)."""
    return bool(re.match(r"^(0[0-9]{5}|3[0-9]{5}|6[0-9]{5})$", symbol))


def _is_us_ticker(symbol: str) -> bool:
    """Check if symbol looks like a Western ticker (letters only)."""
    return bool(re.match(r"^[A-Za-z]{1,6}$", symbol))


def _is_csi_index(symbol: str) -> bool:
    """Check if symbol is a known Chinese index code."""
    return symbol in ("000300", "000016", "000905", "399001", "399006", "000001")


def _fetch_real_a_share(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch real-time A-share market data via akshare.

    Uses the free EastMoney spot API through akshare.
    Returns None on any error (network, timeout, missing symbol).
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]

        # ak.stock_zh_a_spot_em() returns a DataFrame with all A-shares
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            logger.warning("[tools] akshare returned empty DataFrame")
            return None

        # Filter by symbol code
        row = df[df["代码"] == symbol]
        if row.empty:
            logger.info("[tools] Symbol %s not found in akshare spot data", symbol)
            return None

        r = row.iloc[0]
        price = float(r.get("最新价", 0)) if r.get("最新价") else None
        change_pct = float(r.get("涨跌幅", 0)) if r.get("涨跌幅") else None
        change_amt = float(r.get("涨跌额", 0)) if r.get("涨跌额") else None
        pe_ttm = float(r.get("市盈率-动态", 0)) if r.get("市盈率-动态") else None
        pb = float(r.get("市净率", 0)) if r.get("市净率") else None
        volume = float(r.get("成交量", 0)) if r.get("成交量") else None
        turnover = float(r.get("成交额", 0)) if r.get("成交额") else None
        market_cap = float(r.get("总市值", 0)) if r.get("总市值") else None
        high = float(r.get("最高", 0)) if r.get("最高") else None
        low = float(r.get("最低", 0)) if r.get("最低") else None

        logger.info("[tools] akshare → %s price=%s change=%.2f%%", symbol, price, change_pct or 0)

        return {
            "symbol": f"{symbol}.{'SH' if symbol.startswith('6') else 'SZ'}",
            "name": str(r.get("名称", "")),
            "name_cn": str(r.get("名称", "")),
            "sector": "N/A",
            "price": price or 0.0,
            "change": change_amt or 0.0,
            "change_pct": change_pct or 0.0,
            "volume": volume,
            "avg_volume_30d": None,
            "market_cap_bn_cny": round(market_cap / 1e9, 2) if market_cap else None,
            "pe_ttm": pe_ttm,
            "pb": pb,
            "dividend_yield": None,
            "52w_high": high,
            "52w_low": low,
            "beta": None,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "source": "akshare (real-time)",
        }

    except ImportError:
        logger.debug("[tools] akshare not installed — skipping real A-share fetch")
        return None
    except Exception as exc:
        logger.warning("[tools] akshare fetch failed for %s: %s", symbol, exc)
        return None


def _fetch_real_us_stock(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch real-time US stock data via yfinance.

    Returns None on any error.
    """
    try:
        import yfinance as yf  # type: ignore[import-untyped]

        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        fast_info = getattr(ticker, "fast_info", None)

        price = None
        change_pct = None
        if fast_info is not None:
            try:
                price = float(fast_info.get("lastPrice", 0) or 0)
                prev_close = float(fast_info.get("previousClose", 0) or 0)
                if prev_close and price:
                    change_pct = round((price - prev_close) / prev_close * 100, 2)
            except Exception:
                pass

        if price is None:
            price = float(info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0)
        if change_pct is None:
            change_pct_raw = info.get("regularMarketChangePercent")
            if change_pct_raw is not None:
                change_pct = round(float(change_pct_raw), 2)

        logger.info("[tools] yfinance → %s price=%s change=%.2f%%", symbol, price, change_pct or 0)

        return {
            "symbol": symbol,
            "name": str(info.get("longName", info.get("shortName", symbol))),
            "name_cn": str(info.get("longName", "")),
            "sector": str(info.get("sector", "N/A")),
            "price": price or 0.0,
            "change": round(float(info.get("regularMarketChange", 0) or 0), 2),
            "change_pct": change_pct or 0.0,
            "volume": int(info.get("volume", 0) or 0),
            "avg_volume_30d": int(info.get("averageVolume", 0) or 0),
            "market_cap_bn_cny": None,
            "pe_ttm": float(info.get("trailingPE", 0)) if info.get("trailingPE") else None,
            "pb": float(info.get("priceToBook", 0)) if info.get("priceToBook") else None,
            "dividend_yield": round(float(info.get("dividendYield", 0) or 0) * 100, 2) if info.get("dividendYield") else None,
            "52w_high": float(info.get("fiftyTwoWeekHigh", 0)) if info.get("fiftyTwoWeekHigh") else None,
            "52w_low": float(info.get("fiftyTwoWeekLow", 0)) if info.get("fiftyTwoWeekLow") else None,
            "beta": float(info.get("beta", 0)) if info.get("beta") else None,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "source": "yfinance (real-time)",
        }

    except ImportError:
        logger.debug("[tools] yfinance not installed — skipping real US stock fetch")
        return None
    except Exception as exc:
        logger.warning("[tools] yfinance fetch failed for %s: %s", symbol, exc)
        return None


def _fetch_real_csi_index(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch real-time Chinese index data (CSI 300, SSE Composite, etc.).

    Returns None on any error.
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]

        # Map known index codes to akshare index codes
        index_map = {
            "000300": "sh000300",   # CSI 300
            "000016": "sh000016",   # SSE 50
            "000905": "sh000905",   # CSI 500
            "399001": "sz399001",   # SZSE Component
            "399006": "sz399006",   # ChiNext
            "000001": "sh000001",   # SSE Composite
        }

        ak_code = index_map.get(symbol)
        if not ak_code:
            return None

        df = ak.stock_zh_index_daily_em(symbol=ak_code)
        if df is None or df.empty:
            logger.warning("[tools] akshare index fetch empty for %s", symbol)
            return None

        latest = df.iloc[-1]
        # stock_zh_index_daily_em returns historical daily data; we take the latest row
        close = float(latest.get("close", 0))

        index_names = {
            "000300": ("CSI 300 Index", "沪深300"),
            "000016": ("SSE 50 Index", "上证50"),
            "000905": ("CSI 500 Index", "中证500"),
            "399001": ("SZSE Component Index", "深证成指"),
            "399006": ("ChiNext Index", "创业板指"),
            "000001": ("SSE Composite Index", "上证综指"),
        }
        name_en, name_cn = index_names.get(symbol, (f"Index {symbol}", f"指数{symbol}"))

        logger.info("[tools] akshare index → %s close=%s", symbol, close)

        return {
            "symbol": symbol,
            "name": name_en,
            "name_cn": name_cn,
            "sector": "Broad Market",
            "price": close,
            "change": float(latest.get("change", 0) or 0),
            "change_pct": float(latest.get("pct_chg", 0) or 0),
            "volume": float(latest.get("volume", 0) or 0),
            "avg_volume_30d": None,
            "market_cap_bn_cny": None,
            "pe_ttm": None,
            "pb": None,
            "dividend_yield": None,
            "52w_high": float(latest.get("high", 0) or 0),
            "52w_low": float(latest.get("low", 0) or 0),
            "beta": None,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "source": "akshare (real-time index)",
        }

    except Exception as exc:
        logger.warning("[tools] akshare index fetch failed for %s: %s", symbol, exc)
        return None


# ═══════════════════════════════════════════════════════════════
# Mock market database (OpenBB-style structured data)
# ═══════════════════════════════════════════════════════════════
#
# Used as FALLBACK when real-time data sources are unavailable.
# In production this would be replaced by a live API call via
# OpenBB SDK or an internal data pipeline (Wind / EastMoney / Tushare).

_MOCK_MARKET_DB: Dict[str, Dict[str, Any]] = {
    "600519": {
        "symbol": "600519.SS",
        "name": "Kweichow Moutai",
        "name_cn": "贵州茅台",
        "sector": "Consumer Staples / Baijiu",
        "price": 1680.50,
        "change": -12.30,
        "change_pct": -0.73,
        "volume": 2_340_000,
        "avg_volume_30d": 3_100_000,
        "market_cap_bn_cny": 2110.0,
        "pe_ttm": 28.4,
        "pb": 8.9,
        "dividend_yield": 1.82,
        "52w_high": 1950.00,
        "52w_low": 1420.00,
        "beta": 0.62,
        "updated_utc": "2026-07-18T09:30:00Z",
    },
    "000300": {
        "symbol": "000300.SS",
        "name": "CSI 300 Index",
        "name_cn": "沪深300",
        "sector": "Broad Market",
        "price": 3987.45,
        "change": 23.15,
        "change_pct": 0.58,
        "volume": None,
        "avg_volume_30d": None,
        "market_cap_bn_cny": None,
        "pe_ttm": 13.2,
        "pb": 1.41,
        "dividend_yield": 2.65,
        "52w_high": 4350.00,
        "52w_low": 3520.00,
        "beta": 1.00,
        "updated_utc": "2026-07-18T09:30:00Z",
    },
    "NVDA": {
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "name_cn": "英伟达",
        "sector": "Technology / Semiconductors",
        "price": 142.80,
        "change": 3.45,
        "change_pct": 2.48,
        "volume": 52_000_000,
        "avg_volume_30d": 48_500_000,
        "market_cap_bn_cny": None,
        "pe_ttm": 55.2,
        "pb": 22.1,
        "dividend_yield": 0.03,
        "52w_high": 155.00,
        "52w_low": 95.00,
        "beta": 1.72,
        "updated_utc": "2026-07-17T20:00:00Z",
    },
}


@_tool
def fetch_market_data(symbol: str) -> Dict[str, Any]:
    """Fetch structured market data for a given ticker.

    OPENBB-STYLE INTERFACE
    ──────────────────────
    Returns a flat dictionary of deterministic market facts:
    price, change %, valuation ratios, volume, 52-week range, etc.

    This is PURE DATA — no analysis, no narrative, no recommendation.

    DATA SOURCE STRATEGY:
      1. A-share codes (6 digits) → akshare (real-time)
      2. CSI indexes → akshare index API
      3. US tickers → yfinance (real-time)
      4. Unknown → mock fallback

    Args:
        symbol: Ticker code (e.g. '600519', '000300', 'NVDA').

    Returns:
        dict with keys: symbol, name, name_cn, sector, price, change,
        change_pct, pe_ttm, pb, dividend_yield, 52w_high, 52w_low,
        beta, updated_utc.  Returns error dict if symbol not found.
    """
    key = symbol.upper().strip()

    # ── Try real-time data first ──
    real_data: Optional[Dict[str, Any]] = None

    if _is_a_share(key):
        real_data = _fetch_real_a_share(key)
    elif _is_csi_index(key):
        real_data = _fetch_real_csi_index(key)
    elif _is_us_ticker(key):
        real_data = _fetch_real_us_stock(key)

    if real_data is not None:
        return {"status": "ok", **real_data}

    # ── Fallback 1: known mock symbols ──
    if key in _MOCK_MARKET_DB:
        logger.info("[tools] Using mock data for %s (known symbol, real fetch unavailable)", key)
        return {"status": "ok", **_MOCK_MARKET_DB[key]}

    # ── Fallback 2: Graceful degradation — unknown symbols return a structured stub ──
    logger.info("[tools] Symbol %s not found in any data source — returning limited stub", key)
    return {
        "status": "limited",
        "symbol": key,
        "name": f"Unknown ({key})",
        "name_cn": f"未知 ({key})",
        "sector": "N/A",
        "price": round(_rng.uniform(10, 500), 2),
        "change": round(_rng.uniform(-15, 15), 2),
        "change_pct": round(_rng.uniform(-3, 3), 2),
        "volume": _rng.randint(500_000, 10_000_000),
        "avg_volume_30d": _rng.randint(500_000, 10_000_000),
        "market_cap_bn_cny": None,
        "pe_ttm": round(_rng.uniform(5, 80), 1),
        "pb": round(_rng.uniform(0.5, 15), 2),
        "dividend_yield": round(_rng.uniform(0, 5), 2),
        "52w_high": round(_rng.uniform(20, 600), 2),
        "52w_low": round(_rng.uniform(10, 300), 2),
        "beta": round(_rng.uniform(0.3, 2.5), 2),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Mock data — symbol not in real-time or demo database.",
    }


# ═══════════════════════════════════════════════════════════════
# Mock RAG document store (FinRAG-style hybrid retrieval)
# ═══════════════════════════════════════════════════════════════
#
# FinRAG's key insight: combine dense (semantic) retrieval with
# sparse (BM25 / keyword) retrieval, then merge & re-rank.
# This mock simulates that pipeline with hardcoded snippets.

_MOCK_DOCUMENTS: List[Dict[str, Any]] = [
    # --- Macro / Policy ---
    {
        "id": "doc-001",
        "title": "PBOC Q3 2026 Monetary Policy Report",
        "source": "People's Bank of China",
        "date": "2026-07-10",
        "snippet": (
            "The People's Bank of China maintained its benchmark 1Y LPR at 3.10% "
            "and 5Y+ LPR at 3.60%. The central bank signaled a 'moderately accommodative' "
            "stance, citing subdued CPI (+0.3% YoY) and a gradual recovery in domestic demand."
        ),
        "keywords": ["PBOC", "LPR", "monetary policy", "interest rate", "CPI"],
    },
    {
        "id": "doc-002",
        "title": "CSRC Notice on AI-Generated Investment Advice",
        "source": "China Securities Regulatory Commission",
        "date": "2026-06-28",
        "snippet": (
            "The CSRC reiterated that AI-generated financial advice must be clearly "
            "labeled as 'assistive only.' Any promise of absolute returns or "
            "claims of zero-risk investment constitutes a violation of Article 25 "
            "of the Securities Investment Advisory Regulations."
        ),
        "keywords": ["CSRC", "compliance", "AI advice", "regulatory", "risk disclosure"],
    },
    # --- Sector Research ---
    {
        "id": "doc-003",
        "title": "China EV Battery Sector — H1 2026 Review",
        "source": "CITIC Securities Research",
        "date": "2026-07-15",
        "snippet": (
            "CATL maintained ~44% domestic market share in H1 2026. Lithium carbonate "
            "prices stabilized at ¥95,000–105,000/ton. The sector faces margin compression "
            "from overcapacity (utilization rate ~62%) and ongoing price wars among tier-2 "
            "battery makers. Export growth to Europe (+38% YoY) partially offsets domestic headwinds."
        ),
        "keywords": ["EV", "battery", "CATL", "lithium", "new energy", "NEV"],
    },
    {
        "id": "doc-004",
        "title": "CSI 300 Sector Rotation — Technical Analysis",
        "source": "Huatai Securities",
        "date": "2026-07-14",
        "snippet": (
            "Defensive sectors (consumer staples, utilities) outperformed cyclicals by "
            "420 bps in the past month. The CSI 300 currently trades at 13.2x forward P/E, "
            "near its 5-year median of 12.8x. Analysts note elevated put/call ratios "
            "suggesting increased hedging activity ahead of Q2 earnings season."
        ),
        "keywords": ["CSI 300", "sector rotation", "defensive", "P/E", "technical"],
    },
    # --- Retail Investor Guidance ---
    {
        "id": "doc-005",
        "title": "Guide: Understanding Market Volatility",
        "source": "Shanghai Stock Exchange Investor Education",
        "date": "2026-05-20",
        "snippet": (
            "Market corrections of 10–20% occur on average every 2–3 years in the A-share "
            "market. Historical data shows that investors who maintained their positions "
            "through corrections recovered losses within 12–18 months on average. "
            "Diversification across asset classes and regular rebalancing are the "
            "most effective strategies for managing volatility risk."
        ),
        "keywords": ["volatility", "correction", "investor education", "diversification", "risk"],
    },
    {
        "id": "doc-006",
        "title": "Q2 2026 Fund Flow Analysis — A-Share Market",
        "source": "China Merchants Securities",
        "date": "2026-07-16",
        "snippet": (
            "Northbound net inflows totaled ¥28.7 billion in Q2 2026, concentrated in "
            "consumer staples and industrial automation. Domestic mutual fund subscription "
            "volumes declined 12% QoQ. ETF inflows hit a record ¥156 billion, dominated "
            "by CSI 300 and STAR 50 index products. Retail investor sentiment index "
            "registered 42/100 (cautious zone)."
        ),
        "keywords": ["fund flow", "northbound", "ETF", "retail sentiment", "mutual fund"],
    },
]


def _sparse_score(doc_keywords: List[str], query_terms: List[str]) -> float:
    """BM25-style keyword overlap score (simplified mock).

    In production FinRAG would use a proper inverted index (e.g. Elasticsearch).
    """
    if not query_terms:
        return 0.0
    hits = sum(1 for kw in doc_keywords for qt in query_terms if qt.lower() in kw.lower())
    return hits / max(len(query_terms), 1)


def _dense_score(doc_snippet: str, query: str) -> float:
    """Mock semantic similarity score.

    In production FinRAG would use cosine similarity over BGE-large-zh embeddings.
    Here we approximate with keyword overlap + a jitter for tie-breaking.
    """
    query_lower = query.lower()
    # Count overlapping Chinese/English tokens
    snippet_lower = doc_snippet.lower()
    # Simple n-gram overlap proxy
    query_chunks = set(query_lower.split())
    snippet_chunks = set(snippet_lower.split())
    overlap = len(query_chunks & snippet_chunks)
    base = overlap / max(len(query_chunks), 1) if query_chunks else 0.0
    # Small deterministic jitter so no two docs tie
    jitter = (hash(doc_snippet) % 100) / 1000.0
    return base + jitter


@_tool
def hybrid_retrieve(query: str, top_k: int = 3) -> Dict[str, Any]:
    """Hybrid dense + sparse document retrieval over the financial knowledge base.

    FinRAG-STYLE INTERFACE
    ──────────────────────
    1. Dense pass  — semantic similarity against document embeddings (mocked)
    2. Sparse pass — BM25 keyword matching against title + keywords (mocked)
    3. Merge       — weighted reciprocal rank fusion (WRF)
    4. Return top-k deduplicated snippets

    This returns FACTS AND CONTEXT only — NO advice generation.

    Args:
        query:  Natural-language search query.
        top_k:  Number of top documents to return (default 3).

    Returns:
        dict with keys:
          - status:   "ok"
          - results:  list of {title, source, date, snippet, relevance_score}
          - method:   "hybrid (dense + sparse)"
    """
    # --- Tokenize query for sparse pass ---
    query_terms: List[str] = re.findall(r"[一-鿿]+|[a-zA-Z]+", query)

    # --- Score every document ---
    scored: List[Dict[str, Any]] = []
    for doc in _MOCK_DOCUMENTS:
        d_score = _dense_score(doc["snippet"], query)
        s_score = _sparse_score(doc.get("keywords", []), query_terms)
        # Weighted Reciprocal Rank Fusion (WRF)
        combined = 0.6 * d_score + 0.4 * s_score
        scored.append({
            "title": doc["title"],
            "source": doc["source"],
            "date": doc["date"],
            "snippet": doc["snippet"],
            "relevance_score": round(combined, 4),
        })

    # --- Sort descending & take top-k ---
    scored.sort(key=lambda d: d["relevance_score"], reverse=True)
    top = scored[:top_k]

    return {
        "status": "ok",
        "results": top,
        "method": "hybrid (dense + sparse)",
        "query": query,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# Web Search — real-time information retrieval
# ═══════════════════════════════════════════════════════════════
#
# Provides a free, no-API-key web search capability using DuckDuckGo's
# Instant Answer API. Falls back gracefully when network is unavailable.
#
# In production, this can be swapped for Bing Search API, SerpAPI, or
# a specialised financial news aggregator.


_WEB_SEARCH_TIMEOUT = float(os.getenv("WEB_SEARCH_TIMEOUT", "8.0"))
_WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() in ("1", "true", "yes")


def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search the web for real-time financial information.

    Uses DuckDuckGo's free Instant Answer API (no API key required).
    Returns structured results that the Empathy Copilot can incorporate
    into its narrative.

    This is a SYNCHRONOUS function by design — it's called from the
    Quantitative Researcher node which runs tools only (no LLM),
    keeping the FinRobot separation clean.

    Args:
        query:      Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: title, url, snippet. Empty list on error
        or when web search is disabled.
    """
    if not _WEB_SEARCH_ENABLED:
        logger.debug("[tools] Web search disabled via WEB_SEARCH_ENABLED env var")
        return []

    results: List[Dict[str, str]] = []

    try:
        import urllib.parse

        import httpx

        # DuckDuckGo Instant Answer API (free, no API key)
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

        with httpx.Client(timeout=_WEB_SEARCH_TIMEOUT) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        # Extract Abstract (primary answer)
        abstract: str = (data.get("Abstract") or "").strip()
        abstract_url: str = (data.get("AbstractURL") or "").strip()
        if abstract:
            results.append({
                "title": data.get("Heading", "Search Result"),
                "url": abstract_url,
                "snippet": abstract[:500] if len(abstract) > 500 else abstract,
            })

        # Extract Related Topics
        for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
            if isinstance(topic, dict):
                text = (topic.get("Text") or "").strip()
                url_topic = (topic.get("FirstURL") or "").strip()
                if text:
                    results.append({
                        "title": text.split(" - ")[0] if " - " in text else "Related",
                        "url": url_topic,
                        "snippet": text[:500],
                    })

        if results:
            logger.info("[tools] Web search: %d results for '%s'", len(results), query[:60])
        else:
            logger.info("[tools] Web search: no results for '%s'", query[:60])

    except ImportError:
        logger.debug("[tools] httpx not available for web search")
    except Exception as exc:
        logger.warning("[tools] Web search failed for '%s': %s", query[:60], exc)

    return results


def web_search_formatted(query: str, max_results: int = 5) -> str:
    """Convenience wrapper: returns web search results as a formatted string.

    Useful for injecting into LLM prompts directly.
    """
    results = web_search(query, max_results=max_results)
    if not results:
        return ""

    lines = ["**🌐 实时网络搜索 / Live Web Search**"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r['title']}**")
        lines.append(f"   {r['snippet']}")
        if r.get("url"):
            lines.append(f"   🔗 {r['url']}")
    return "\n".join(lines)


# ── Expose web_search as a tool (LangChain-compatible) ──
@_tool
def web_search_tool(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search the web for current financial news and information.

    Returns structured search results for use by the agent pipeline.
    """
    results = web_search(query, max_results=max_results)
    return {
        "status": "ok" if results else "no_results",
        "results": results,
        "query": query,
        "searched_at": datetime.now(timezone.utc).isoformat(),
    }
