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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("smartcycle.tools")

# ── Thread pool for running sync functions in async contexts ──
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tools_")

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

    Uses akshare's spot/real-time API (stock_zh_index_spot_em) for live data,
    falling back to daily historical if the spot API is unavailable.

    Returns None on any error.
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]

        index_names = {
            "000300": ("CSI 300 Index", "沪深300"),
            "000016": ("SSE 50 Index", "上证50"),
            "000905": ("CSI 500 Index", "中证500"),
            "399001": ("SZSE Component Index", "深证成指"),
            "399006": ("ChiNext Index", "创业板指"),
            "000001": ("SSE Composite Index", "上证综指"),
        }
        name_en, name_cn = index_names.get(symbol, (f"Index {symbol}", f"指数{symbol}"))

        # ── Try real-time spot API first ──
        try:
            df_spot = ak.stock_zh_index_spot_em()
            if df_spot is not None and not df_spot.empty:
                # Match by index name (Chinese)
                row = df_spot[df_spot["名称"] == name_cn]
                if not row.empty:
                    r = row.iloc[0]
                    price = float(r.get("最新价", 0)) if r.get("最新价") else 0.0
                    change = float(r.get("涨跌额", 0)) if r.get("涨跌额") else 0.0
                    change_pct = float(r.get("涨跌幅", 0)) if r.get("涨跌幅") else 0.0
                    volume = float(r.get("成交量", 0)) if r.get("成交量") else 0.0
                    turnover = float(r.get("成交额", 0)) if r.get("成交额") else 0.0

                    logger.info("[tools] akshare spot index → %s price=%s change=%.2f%%", symbol, price, change_pct)

                    return {
                        "symbol": symbol,
                        "name": name_en,
                        "name_cn": name_cn,
                        "sector": "Broad Market",
                        "price": price,
                        "change": change,
                        "change_pct": change_pct,
                        "volume": volume,
                        "avg_volume_30d": None,
                        "market_cap_bn_cny": None,
                        "pe_ttm": None,
                        "pb": None,
                        "dividend_yield": None,
                        "52w_high": None,
                        "52w_low": None,
                        "beta": None,
                        "updated_utc": datetime.now(timezone.utc).isoformat(),
                        "source": "akshare (real-time spot index)",
                    }
        except Exception as spot_err:
            logger.debug("[tools] Spot index API failed for %s, trying daily fallback: %s", symbol, spot_err)

        # ── Fallback: daily historical API ──
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
            logger.warning("[tools] akshare index daily fetch empty for %s", symbol)
            return None

        latest = df.iloc[-1]
        close = float(latest.get("close", 0))

        logger.info("[tools] akshare index daily fallback → %s close=%s", symbol, close)

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
            "source": "akshare (daily historical index)",
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
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Consumer Staples / Baijiu (消费/白酒)
    # ══════════════════════════════════════════════════════════════
    "600519": {
        "symbol": "600519.SH", "name": "Kweichow Moutai", "name_cn": "贵州茅台",
        "sector": "Consumer Staples / Baijiu",
        "price": 1680.50, "change": -12.30, "change_pct": -0.73,
        "volume": 2_340_000, "avg_volume_30d": 3_100_000,
        "market_cap_bn_cny": 2110.0, "pe_ttm": 28.4, "pb": 8.9,
        "dividend_yield": 1.82, "52w_high": 1950.00, "52w_low": 1420.00,
        "beta": 0.62, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "000858": {
        "symbol": "000858.SZ", "name": "Wuliangye Yibin", "name_cn": "五粮液",
        "sector": "Consumer Staples / Baijiu",
        "price": 142.30, "change": -1.85, "change_pct": -1.28,
        "volume": 18_500_000, "avg_volume_30d": 16_200_000,
        "market_cap_bn_cny": 552.0, "pe_ttm": 18.2, "pb": 4.8,
        "dividend_yield": 2.45, "52w_high": 178.00, "52w_low": 122.00,
        "beta": 0.78, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "600887": {
        "symbol": "600887.SH", "name": "Inner Mongolia Yili", "name_cn": "伊利股份",
        "sector": "Consumer Staples / Dairy",
        "price": 28.45, "change": 0.32, "change_pct": 1.14,
        "volume": 35_200_000, "avg_volume_30d": 38_100_000,
        "market_cap_bn_cny": 181.0, "pe_ttm": 15.8, "pb": 3.2,
        "dividend_yield": 3.85, "52w_high": 32.50, "52w_low": 22.80,
        "beta": 0.55, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — New Energy / EV (新能源/电动车)
    # ══════════════════════════════════════════════════════════════
    "300750": {
        "symbol": "300750.SZ", "name": "CATL (Contemporary Amperex)", "name_cn": "宁德时代",
        "sector": "New Energy / Battery",
        "price": 218.50, "change": 4.20, "change_pct": 1.96,
        "volume": 22_800_000, "avg_volume_30d": 24_500_000,
        "market_cap_bn_cny": 962.0, "pe_ttm": 22.4, "pb": 5.2,
        "dividend_yield": 0.85, "52w_high": 280.00, "52w_low": 165.00,
        "beta": 1.28, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "002594": {
        "symbol": "002594.SZ", "name": "BYD Company", "name_cn": "比亚迪",
        "sector": "New Energy / EV",
        "price": 312.80, "change": -5.40, "change_pct": -1.70,
        "volume": 11_200_000, "avg_volume_30d": 10_800_000,
        "market_cap_bn_cny": 910.0, "pe_ttm": 35.6, "pb": 6.8,
        "dividend_yield": 0.48, "52w_high": 368.00, "52w_low": 218.00,
        "beta": 1.42, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "601012": {
        "symbol": "601012.SH", "name": "LONGi Green Energy", "name_cn": "隆基绿能",
        "sector": "New Energy / Solar",
        "price": 15.78, "change": 0.45, "change_pct": 2.94,
        "volume": 85_400_000, "avg_volume_30d": 78_200_000,
        "market_cap_bn_cny": 119.0, "pe_ttm": 14.2, "pb": 1.55,
        "dividend_yield": 1.20, "52w_high": 26.50, "52w_low": 11.20,
        "beta": 1.18, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "300274": {
        "symbol": "300274.SZ", "name": "Sungrow Power Supply", "name_cn": "阳光电源",
        "sector": "New Energy / Inverter",
        "price": 85.60, "change": 2.15, "change_pct": 2.58,
        "volume": 15_800_000, "avg_volume_30d": 14_200_000,
        "market_cap_bn_cny": 178.0, "pe_ttm": 24.8, "pb": 5.6,
        "dividend_yield": 0.55, "52w_high": 112.00, "52w_low": 62.00,
        "beta": 1.35, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Semiconductor / Chip (半导体/芯片)
    # ══════════════════════════════════════════════════════════════
    "688981": {
        "symbol": "688981.SH", "name": "SMIC (Semiconductor Mfg Int'l)", "name_cn": "中芯国际",
        "sector": "Technology / Semiconductor",
        "price": 52.30, "change": -0.85, "change_pct": -1.60,
        "volume": 42_100_000, "avg_volume_30d": 45_500_000,
        "market_cap_bn_cny": 415.0, "pe_ttm": 58.2, "pb": 3.8,
        "dividend_yield": 0.00, "52w_high": 72.00, "52w_low": 38.50,
        "beta": 1.55, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "002371": {
        "symbol": "002371.SZ", "name": "NAURA Technology Group", "name_cn": "北方华创",
        "sector": "Technology / Semiconductor Equipment",
        "price": 425.60, "change": 8.30, "change_pct": 1.99,
        "volume": 4_200_000, "avg_volume_30d": 3_800_000,
        "market_cap_bn_cny": 225.0, "pe_ttm": 48.5, "pb": 10.2,
        "dividend_yield": 0.22, "52w_high": 498.00, "52w_low": 280.00,
        "beta": 1.42, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "603986": {
        "symbol": "603986.SH", "name": "GigaDevice Semiconductor", "name_cn": "兆易创新",
        "sector": "Technology / Memory Chips",
        "price": 88.90, "change": 1.55, "change_pct": 1.77,
        "volume": 7_500_000, "avg_volume_30d": 6_900_000,
        "market_cap_bn_cny": 59.2, "pe_ttm": 38.5, "pb": 5.4,
        "dividend_yield": 0.35, "52w_high": 112.00, "52w_low": 58.00,
        "beta": 1.52, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "688012": {
        "symbol": "688012.SH", "name": "AMEC (Advanced Micro-Fab)", "name_cn": "中微公司",
        "sector": "Technology / Etch Equipment",
        "price": 162.40, "change": -2.10, "change_pct": -1.28,
        "volume": 3_200_000, "avg_volume_30d": 3_500_000,
        "market_cap_bn_cny": 100.3, "pe_ttm": 65.0, "pb": 8.8,
        "dividend_yield": 0.12, "52w_high": 195.00, "52w_low": 115.00,
        "beta": 1.38, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Banking / Financials (银行/金融)
    # ══════════════════════════════════════════════════════════════
    "601398": {
        "symbol": "601398.SH", "name": "ICBC (Ind. & Comm. Bank of China)", "name_cn": "工商银行",
        "sector": "Financials / Banking",
        "price": 5.82, "change": 0.02, "change_pct": 0.34,
        "volume": 125_600_000, "avg_volume_30d": 132_000_000,
        "market_cap_bn_cny": 2075.0, "pe_ttm": 5.8, "pb": 0.62,
        "dividend_yield": 5.85, "52w_high": 6.55, "52w_low": 4.52,
        "beta": 0.42, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "600036": {
        "symbol": "600036.SH", "name": "China Merchants Bank", "name_cn": "招商银行",
        "sector": "Financials / Banking",
        "price": 38.25, "change": 0.55, "change_pct": 1.46,
        "volume": 52_300_000, "avg_volume_30d": 48_700_000,
        "market_cap_bn_cny": 965.0, "pe_ttm": 6.8, "pb": 1.05,
        "dividend_yield": 4.52, "52w_high": 44.00, "52w_low": 29.50,
        "beta": 0.75, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "601318": {
        "symbol": "601318.SH", "name": "Ping An Insurance", "name_cn": "中国平安",
        "sector": "Financials / Insurance",
        "price": 48.90, "change": 0.78, "change_pct": 1.62,
        "volume": 42_100_000, "avg_volume_30d": 45_300_000,
        "market_cap_bn_cny": 892.0, "pe_ttm": 9.2, "pb": 1.15,
        "dividend_yield": 4.10, "52w_high": 56.00, "52w_low": 38.00,
        "beta": 0.82, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Healthcare / Pharma (医药/医疗)
    # ══════════════════════════════════════════════════════════════
    "600276": {
        "symbol": "600276.SH", "name": "Jiangsu Hengrui Medicine", "name_cn": "恒瑞医药",
        "sector": "Healthcare / Pharma",
        "price": 52.30, "change": 0.85, "change_pct": 1.65,
        "volume": 18_200_000, "avg_volume_30d": 16_800_000,
        "market_cap_bn_cny": 334.0, "pe_ttm": 42.5, "pb": 7.8,
        "dividend_yield": 0.65, "52w_high": 62.00, "52w_low": 35.00,
        "beta": 0.72, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "300760": {
        "symbol": "300760.SZ", "name": "Mindray Medical", "name_cn": "迈瑞医疗",
        "sector": "Healthcare / Medical Devices",
        "price": 315.80, "change": 2.40, "change_pct": 0.77,
        "volume": 2_800_000, "avg_volume_30d": 3_100_000,
        "market_cap_bn_cny": 382.0, "pe_ttm": 32.8, "pb": 9.5,
        "dividend_yield": 1.10, "52w_high": 368.00, "52w_low": 252.00,
        "beta": 0.58, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "000538": {
        "symbol": "000538.SZ", "name": "Yunnan Baiyao Group", "name_cn": "云南白药",
        "sector": "Healthcare / TCM",
        "price": 58.20, "change": -0.30, "change_pct": -0.51,
        "volume": 5_600_000, "avg_volume_30d": 5_200_000,
        "market_cap_bn_cny": 104.5, "pe_ttm": 22.5, "pb": 3.8,
        "dividend_yield": 2.15, "52w_high": 68.00, "52w_low": 46.50,
        "beta": 0.48, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "300015": {
        "symbol": "300015.SZ", "name": "Aier Eye Hospital Group", "name_cn": "爱尔眼科",
        "sector": "Healthcare / Hospital Chain",
        "price": 23.85, "change": 0.42, "change_pct": 1.79,
        "volume": 26_400_000, "avg_volume_30d": 24_800_000,
        "market_cap_bn_cny": 222.0, "pe_ttm": 52.0, "pb": 11.5,
        "dividend_yield": 0.35, "52w_high": 32.00, "52w_low": 17.50,
        "beta": 0.92, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Technology / AI (科技/AI)
    # ══════════════════════════════════════════════════════════════
    "002230": {
        "symbol": "002230.SZ", "name": "iFLYTEK", "name_cn": "科大讯飞",
        "sector": "Technology / AI",
        "price": 52.80, "change": 1.25, "change_pct": 2.42,
        "volume": 28_500_000, "avg_volume_30d": 25_200_000,
        "market_cap_bn_cny": 122.0, "pe_ttm": 85.0, "pb": 7.2,
        "dividend_yield": 0.15, "52w_high": 68.00, "52w_low": 38.00,
        "beta": 1.28, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "300033": {
        "symbol": "300033.SZ", "name": "Hithink RoyalFlush", "name_cn": "同花顺",
        "sector": "Technology / Fintech",
        "price": 158.30, "change": -3.20, "change_pct": -1.98,
        "volume": 8_200_000, "avg_volume_30d": 9_100_000,
        "market_cap_bn_cny": 85.2, "pe_ttm": 45.5, "pb": 12.8,
        "dividend_yield": 0.28, "52w_high": 205.00, "52w_low": 112.00,
        "beta": 1.55, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Automotive (汽车)
    # ══════════════════════════════════════════════════════════════
    "000625": {
        "symbol": "000625.SZ", "name": "Changan Automobile", "name_cn": "长安汽车",
        "sector": "Consumer Discretionary / Auto",
        "price": 18.25, "change": 0.58, "change_pct": 3.28,
        "volume": 62_400_000, "avg_volume_30d": 58_200_000,
        "market_cap_bn_cny": 181.0, "pe_ttm": 14.5, "pb": 2.2,
        "dividend_yield": 1.85, "52w_high": 22.50, "52w_low": 11.80,
        "beta": 1.12, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "601238": {
        "symbol": "601238.SH", "name": "GAC Group", "name_cn": "广汽集团",
        "sector": "Consumer Discretionary / Auto",
        "price": 10.45, "change": -0.12, "change_pct": -1.14,
        "volume": 28_500_000, "avg_volume_30d": 30_100_000,
        "market_cap_bn_cny": 109.5, "pe_ttm": 12.8, "pb": 1.28,
        "dividend_yield": 3.20, "52w_high": 13.80, "52w_low": 7.90,
        "beta": 0.95, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Defense / Military (军工)
    # ══════════════════════════════════════════════════════════════
    "600893": {
        "symbol": "600893.SH", "name": "AECC Aviation Power", "name_cn": "航发动力",
        "sector": "Defense / Aero Engine",
        "price": 42.80, "change": 1.15, "change_pct": 2.76,
        "volume": 12_500_000, "avg_volume_30d": 11_200_000,
        "market_cap_bn_cny": 114.0, "pe_ttm": 52.0, "pb": 4.5,
        "dividend_yield": 0.42, "52w_high": 55.00, "52w_low": 30.50,
        "beta": 0.92, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "002013": {
        "symbol": "002013.SZ", "name": "AVIC Electromechanical Systems", "name_cn": "中航机电",
        "sector": "Defense / Avionics",
        "price": 12.35, "change": 0.22, "change_pct": 1.81,
        "volume": 32_100_000, "avg_volume_30d": 30_500_000,
        "market_cap_bn_cny": 47.8, "pe_ttm": 35.2, "pb": 3.1,
        "dividend_yield": 0.75, "52w_high": 16.20, "52w_low": 8.80,
        "beta": 0.88, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Real Estate / Infrastructure (地产/基建)
    # ══════════════════════════════════════════════════════════════
    "000002": {
        "symbol": "000002.SZ", "name": "China Vanke", "name_cn": "万科A",
        "sector": "Real Estate / Developer",
        "price": 8.75, "change": 0.15, "change_pct": 1.74,
        "volume": 85_200_000, "avg_volume_30d": 78_500_000,
        "market_cap_bn_cny": 104.5, "pe_ttm": 12.5, "pb": 0.55,
        "dividend_yield": 4.85, "52w_high": 14.50, "52w_low": 6.20,
        "beta": 1.08, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Mining / Materials (资源/材料)
    # ══════════════════════════════════════════════════════════════
    "601899": {
        "symbol": "601899.SH", "name": "Zijin Mining Group", "name_cn": "紫金矿业",
        "sector": "Materials / Mining",
        "price": 18.25, "change": 0.42, "change_pct": 2.36,
        "volume": 85_600_000, "avg_volume_30d": 80_200_000,
        "market_cap_bn_cny": 480.0, "pe_ttm": 16.5, "pb": 3.2,
        "dividend_yield": 2.20, "52w_high": 20.50, "52w_low": 12.00,
        "beta": 1.05, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Power / Utilities (电力/公用事业)
    # ══════════════════════════════════════════════════════════════
    "600900": {
        "symbol": "600900.SH", "name": "Yangtze Power", "name_cn": "长江电力",
        "sector": "Utilities / Hydro Power",
        "price": 28.50, "change": 0.05, "change_pct": 0.18,
        "volume": 22_100_000, "avg_volume_30d": 24_500_000,
        "market_cap_bn_cny": 697.0, "pe_ttm": 18.5, "pb": 2.8,
        "dividend_yield": 3.95, "52w_high": 31.00, "52w_low": 22.50,
        "beta": 0.35, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share Stocks — Telecom (通信)
    # ══════════════════════════════════════════════════════════════
    "600941": {
        "symbol": "600941.SH", "name": "China Mobile", "name_cn": "中国移动",
        "sector": "Telecom / Operator",
        "price": 108.50, "change": 0.30, "change_pct": 0.28,
        "volume": 15_200_000, "avg_volume_30d": 16_800_000,
        "market_cap_bn_cny": 2325.0, "pe_ttm": 12.5, "pb": 1.45,
        "dividend_yield": 5.20, "52w_high": 118.00, "52w_low": 82.00,
        "beta": 0.38, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # US Stocks
    # ══════════════════════════════════════════════════════════════
    "NVDA": {
        "symbol": "NVDA", "name": "NVIDIA Corporation", "name_cn": "英伟达",
        "sector": "Technology / AI Chips",
        "price": 142.80, "change": 3.45, "change_pct": 2.48,
        "volume": 52_000_000, "avg_volume_30d": 48_500_000,
        "market_cap_bn_cny": None, "pe_ttm": 55.2, "pb": 22.1,
        "dividend_yield": 0.03, "52w_high": 155.00, "52w_low": 95.00,
        "beta": 1.72, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "AAPL": {
        "symbol": "AAPL", "name": "Apple Inc.", "name_cn": "苹果",
        "sector": "Technology / Consumer Electronics",
        "price": 228.50, "change": 1.80, "change_pct": 0.79,
        "volume": 48_200_000, "avg_volume_30d": 52_100_000,
        "market_cap_bn_cny": None, "pe_ttm": 32.5, "pb": 42.0,
        "dividend_yield": 0.52, "52w_high": 245.00, "52w_low": 172.00,
        "beta": 1.22, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "MSFT": {
        "symbol": "MSFT", "name": "Microsoft Corporation", "name_cn": "微软",
        "sector": "Technology / Cloud & AI",
        "price": 485.20, "change": 2.40, "change_pct": 0.50,
        "volume": 18_500_000, "avg_volume_30d": 20_200_000,
        "market_cap_bn_cny": None, "pe_ttm": 38.2, "pb": 14.5,
        "dividend_yield": 0.72, "52w_high": 510.00, "52w_low": 378.00,
        "beta": 0.92, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "TSLA": {
        "symbol": "TSLA", "name": "Tesla Inc.", "name_cn": "特斯拉",
        "sector": "Consumer Discretionary / EV",
        "price": 252.30, "change": -5.80, "change_pct": -2.25,
        "volume": 72_500_000, "avg_volume_30d": 68_200_000,
        "market_cap_bn_cny": None, "pe_ttm": 68.5, "pb": 12.8,
        "dividend_yield": 0.00, "52w_high": 320.00, "52w_low": 160.00,
        "beta": 1.95, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "GOOGL": {
        "symbol": "GOOGL", "name": "Alphabet Inc.", "name_cn": "谷歌/Alphabet",
        "sector": "Technology / Internet & AI",
        "price": 188.40, "change": 0.90, "change_pct": 0.48,
        "volume": 22_100_000, "avg_volume_30d": 24_300_000,
        "market_cap_bn_cny": None, "pe_ttm": 27.8, "pb": 7.2,
        "dividend_yield": 0.35, "52w_high": 205.00, "52w_low": 142.00,
        "beta": 1.15, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "AMZN": {
        "symbol": "AMZN", "name": "Amazon.com Inc.", "name_cn": "亚马逊",
        "sector": "Consumer Discretionary / E-com & Cloud",
        "price": 215.60, "change": 3.20, "change_pct": 1.51,
        "volume": 32_800_000, "avg_volume_30d": 35_100_000,
        "market_cap_bn_cny": None, "pe_ttm": 42.5, "pb": 8.5,
        "dividend_yield": 0.00, "52w_high": 235.00, "52w_low": 155.00,
        "beta": 1.18, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "META": {
        "symbol": "META", "name": "Meta Platforms Inc.", "name_cn": "Meta",
        "sector": "Technology / Social Media",
        "price": 562.80, "change": -2.50, "change_pct": -0.44,
        "volume": 10_500_000, "avg_volume_30d": 11_200_000,
        "market_cap_bn_cny": None, "pe_ttm": 28.5, "pb": 9.2,
        "dividend_yield": 0.42, "52w_high": 610.00, "52w_low": 380.00,
        "beta": 1.28, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    "JPM": {
        "symbol": "JPM", "name": "JPMorgan Chase & Co.", "name_cn": "摩根大通",
        "sector": "Financials / Banking",
        "price": 218.40, "change": 1.55, "change_pct": 0.71,
        "volume": 8_200_000, "avg_volume_30d": 8_800_000,
        "market_cap_bn_cny": None, "pe_ttm": 12.5, "pb": 2.1,
        "dividend_yield": 2.15, "52w_high": 235.00, "52w_low": 165.00,
        "beta": 1.10, "updated_utc": "2026-07-18T20:00:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # Major Chinese Indices (used by /api/v1/market/summary)
    # ══════════════════════════════════════════════════════════════
    "000300": {
        "symbol": "000300", "name": "CSI 300 Index", "name_cn": "沪深300",
        "sector": "Broad Market",
        "price": 3987.45, "change": 23.15, "change_pct": 0.58,
        "volume": None, "avg_volume_30d": None,
        "market_cap_bn_cny": None, "pe_ttm": 13.2, "pb": 1.41,
        "dividend_yield": 2.65, "52w_high": 4350.00, "52w_low": 3520.00,
        "beta": 1.00, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "000001": {
        "symbol": "000001", "name": "SSE Composite Index", "name_cn": "上证综指",
        "sector": "Broad Market",
        "price": 3245.12, "change": -10.08, "change_pct": -0.31,
        "volume": None, "avg_volume_30d": None,
        "market_cap_bn_cny": None, "pe_ttm": 14.1, "pb": 1.35,
        "dividend_yield": 2.80, "52w_high": 3580.00, "52w_low": 2870.00,
        "beta": 1.00, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "399001": {
        "symbol": "399001", "name": "SZSE Component Index", "name_cn": "深证成指",
        "sector": "Broad Market",
        "price": 10782.56, "change": 45.32, "change_pct": 0.42,
        "volume": None, "avg_volume_30d": None,
        "market_cap_bn_cny": None, "pe_ttm": 25.3, "pb": 2.85,
        "dividend_yield": 1.45, "52w_high": 12200.00, "52w_low": 9200.00,
        "beta": 1.12, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "399006": {
        "symbol": "399006", "name": "ChiNext Index", "name_cn": "创业板指",
        "sector": "Broad Market",
        "price": 2156.78, "change": -18.45, "change_pct": -0.85,
        "volume": None, "avg_volume_30d": None,
        "market_cap_bn_cny": None, "pe_ttm": 38.6, "pb": 4.52,
        "dividend_yield": 0.72, "52w_high": 2580.00, "52w_low": 1750.00,
        "beta": 1.35, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "000016": {
        "symbol": "000016", "name": "SSE 50 Index", "name_cn": "上证50",
        "sector": "Broad Market / Large Cap",
        "price": 2685.30, "change": 12.45, "change_pct": 0.47,
        "volume": None, "avg_volume_30d": None,
        "market_cap_bn_cny": None, "pe_ttm": 10.8, "pb": 1.22,
        "dividend_yield": 3.15, "52w_high": 2950.00, "52w_low": 2350.00,
        "beta": 0.88, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "000905": {
        "symbol": "000905", "name": "CSI 500 Index", "name_cn": "中证500",
        "sector": "Broad Market / Mid Cap",
        "price": 6325.80, "change": 28.60, "change_pct": 0.45,
        "volume": None, "avg_volume_30d": None,
        "market_cap_bn_cny": None, "pe_ttm": 22.5, "pb": 2.15,
        "dividend_yield": 1.35, "52w_high": 7200.00, "52w_low": 5250.00,
        "beta": 1.18, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # A-Share ETFs
    # ══════════════════════════════════════════════════════════════
    "510300": {
        "symbol": "510300.SH", "name": "Huatai-PineBridge CSI 300 ETF", "name_cn": "沪深300ETF",
        "sector": "ETF / Broad Market",
        "price": 3.985, "change": 0.023, "change_pct": 0.58,
        "volume": 285_000_000, "avg_volume_30d": 310_000_000,
        "market_cap_bn_cny": 185.0, "pe_ttm": 13.2, "pb": 1.41,
        "dividend_yield": 2.60, "52w_high": 4.350, "52w_low": 3.520,
        "beta": 1.00, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "510050": {
        "symbol": "510050.SH", "name": "ChinaAMC SSE 50 ETF", "name_cn": "上证50ETF",
        "sector": "ETF / Large Cap",
        "price": 2.685, "change": 0.012, "change_pct": 0.45,
        "volume": 165_000_000, "avg_volume_30d": 180_000_000,
        "market_cap_bn_cny": 58.0, "pe_ttm": 10.8, "pb": 1.22,
        "dividend_yield": 3.12, "52w_high": 2.950, "52w_low": 2.350,
        "beta": 0.88, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "510500": {
        "symbol": "510500.SH", "name": "ChinaAMC CSI 500 ETF", "name_cn": "中证500ETF",
        "sector": "ETF / Mid Cap",
        "price": 6.325, "change": 0.028, "change_pct": 0.44,
        "volume": 85_200_000, "avg_volume_30d": 92_100_000,
        "market_cap_bn_cny": 42.0, "pe_ttm": 22.5, "pb": 2.15,
        "dividend_yield": 1.32, "52w_high": 7.200, "52w_low": 5.250,
        "beta": 1.18, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "588000": {
        "symbol": "588000.SH", "name": "ChinaAMC STAR 50 ETF", "name_cn": "科创50ETF",
        "sector": "ETF / Tech Growth",
        "price": 0.952, "change": 0.018, "change_pct": 1.93,
        "volume": 420_000_000, "avg_volume_30d": 380_000_000,
        "market_cap_bn_cny": 68.0, "pe_ttm": 45.2, "pb": 4.85,
        "dividend_yield": 0.35, "52w_high": 1.250, "52w_low": 0.720,
        "beta": 1.52, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "159915": {
        "symbol": "159915.SZ", "name": "E Fund ChiNext ETF", "name_cn": "创业板ETF",
        "sector": "ETF / Growth",
        "price": 2.156, "change": -0.018, "change_pct": -0.83,
        "volume": 225_000_000, "avg_volume_30d": 240_000_000,
        "market_cap_bn_cny": 35.0, "pe_ttm": 38.6, "pb": 4.52,
        "dividend_yield": 0.70, "52w_high": 2.580, "52w_low": 1.750,
        "beta": 1.35, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    # ══════════════════════════════════════════════════════════════
    # Convertible Bonds (可转债)
    # ══════════════════════════════════════════════════════════════
    "113053": {
        "symbol": "113053.SH", "name": "LONGi Green Energy CB", "name_cn": "隆22转债",
        "sector": "Convertible Bond / Solar",
        "price": 112.50, "change": 0.85, "change_pct": 0.76,
        "volume": 8_500_000, "avg_volume_30d": 9_200_000,
        "market_cap_bn_cny": None, "pe_ttm": None, "pb": None,
        "dividend_yield": 0.42, "52w_high": 128.00, "52w_low": 95.00,
        "beta": 0.65, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
    },
    "110079": {
        "symbol": "110079.SH", "name": "Ping An Bank CB", "name_cn": "平银转债",
        "sector": "Convertible Bond / Banking",
        "price": 118.30, "change": -0.15, "change_pct": -0.13,
        "volume": 12_200_000, "avg_volume_30d": 13_500_000,
        "market_cap_bn_cny": None, "pe_ttm": None, "pb": None,
        "dividend_yield": 1.85, "52w_high": 125.00, "52w_low": 102.00,
        "beta": 0.45, "updated_utc": "2026-07-19T09:30:00Z", "source": "mock",
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

    # ── Fallback 2: Unknown symbols — return structured error, NOT fake data ──
    logger.warning("[tools] Symbol '%s' not found in any data source — returning error", key)
    return {
        "status": "error",
        "symbol": key,
        "name": f"Unknown ({key})",
        "name_cn": f"未知代码 ({key})",
        "error": "symbol_not_found",
        "message": f"无法识别代码 '{key}'。请确认代码是否正确。目前Mock数据库覆盖44个标的：A股（白酒、新能源、半导体、银行、医药、科技、汽车、军工、地产、电力、通信共26只）、美股（NVDA/AAPL/MSFT/TSLA/GOOGL/AMZN/META/JPM共8只）、指数（沪深300/上证综指/深证成指/创业板指/上证50/中证500）、ETF（5只）、可转债（2只）。",

        "note": "UNKNOWN SYMBOL — not in real-time or demo database. No fabricated data returned.",
    }


# ═══════════════════════════════════════════════════════════════
# Mock RAG document store (FinRAG-style hybrid retrieval)
# ═══════════════════════════════════════════════════════════════
#
# FinRAG's key insight: combine dense (semantic) retrieval with
# sparse (BM25 / keyword) retrieval, then merge & re-rank.
# This mock simulates that pipeline with hardcoded snippets.

_MOCK_DOCUMENTS: List[Dict[str, Any]] = [
    # ═══ Macro / Policy ═══
    {
        "id": "mock-doc-001",
        "title": "PBOC Q3 2026 Monetary Policy Report",
        "source": "People's Bank of China",
        "date": "2026-07-10",
        "snippet": (
            "The People's Bank of China maintained its benchmark 1Y LPR at 3.10% "
            "and 5Y+ LPR at 3.60%. The central bank signaled a 'moderately accommodative' "
            "stance, citing subdued CPI (+0.3% YoY) and a gradual recovery in domestic demand. "
            "M2 money supply grew 7.2% YoY. RRR stands at 7.0% for large banks, with targeted "
            "cuts for small and micro enterprise lending."
        ),
        "keywords": ["PBOC", "LPR", "monetary policy", "interest rate", "CPI", "RRR", "M2", "央行", "货币政策"],
    },
    {
        "id": "mock-doc-002",
        "title": "CSRC Notice on AI-Generated Investment Advice",
        "source": "China Securities Regulatory Commission",
        "date": "2026-06-28",
        "snippet": (
            "The CSRC reiterated that AI-generated financial advice must be clearly "
            "labeled as 'assistive only.' Any promise of absolute returns or "
            "claims of zero-risk investment constitutes a violation of Article 25 "
            "of the Securities Investment Advisory Regulations. Financial advisors "
            "remain legally responsible for AI-assisted outputs."
        ),
        "keywords": ["CSRC", "compliance", "AI advice", "regulatory", "risk disclosure", "证监会", "合规"],
    },
    {
        "id": "mock-doc-003",
        "title": "China 10Y Bond Yield Hits Historic Low",
        "source": "ChinaBond Pricing Center",
        "date": "2026-07-12",
        "snippet": (
            "China 10-year government bond yield fell to 1.68% in July 2026, a historic low, "
            "reflecting persistently accommodative monetary policy and weak inflation expectations. "
            "Corporate bond default rate declined to 0.35%. Convertible bonds offer attractive "
            "risk-reward with average conversion premium at 30%. LGFV bond spreads compressed "
            "another 30bp as restructuring plans advanced across provinces."
        ),
        "keywords": ["bond", "yield", "债券", "收益率", "interest rate", "LGFV", "城投债", "convertible"],
    },
    # ═══ Sector Research ═══
    {
        "id": "mock-doc-004",
        "title": "China EV Battery Sector — H1 2026 Review",
        "source": "CITIC Securities Research",
        "date": "2026-07-15",
        "snippet": (
            "CATL maintained ~44% domestic market share in H1 2026. Lithium carbonate "
            "prices stabilized at ¥95,000–105,000/ton. The sector faces margin compression "
            "from overcapacity (utilization rate ~62%) and ongoing price wars among tier-2 "
            "battery makers. Export growth to Europe (+38% YoY) partially offsets domestic "
            "headwinds. Solid-state battery pilot production expected Q4 2026."
        ),
        "keywords": ["EV", "battery", "CATL", "lithium", "new energy", "NEV", "新能源", "锂电池", "宁德时代"],
    },
    {
        "id": "mock-doc-005",
        "title": "China Semiconductor Localization — 2026 Progress Report",
        "source": "Semiconductor Industry Association / CSIA",
        "date": "2026-07-08",
        "snippet": (
            "Chinese semiconductor equipment localization rate rose from 25% (2024) to 32% (2026 H1). "
            "SMIC's 7nm (N+2) process reached mass production for Huawei Ascend AI chips. "
            "Key equipment milestones: AMEC's 5nm etching tools qualified at domestic fabs; "
            "NAURA's deposition tools entering 7nm pilot lines. The lithography gap remains — "
            "domestic immersion DUV at 65nm resolution vs ASML's 13.5nm EUV. AI chip demand "
            "surge post-DeepSeek driving unexpected domestic foundry utilization above 85%."
        ),
        "keywords": ["semiconductor", "chip", "半导体", "芯片", "SMIC", "中芯国际", "decoupling", "lithography"],
    },
    {
        "id": "mock-doc-006",
        "title": "CSI 300 Sector Rotation — Q3 2026 Outlook",
        "source": "Huatai Securities",
        "date": "2026-07-14",
        "snippet": (
            "Defensive sectors (consumer staples, utilities) outperformed cyclicals by "
            "420 bps in the past month. The CSI 300 currently trades at 13.2x forward P/E, "
            "near its 5-year median of 12.8x. Analysts note elevated put/call ratios "
            "suggesting increased hedging activity ahead of Q2 earnings season. Overweight "
            "recommendations: healthcare (PE 26x, below 5-year median), consumer staples "
            "(Moutai at attractive valuation). Underweight: real estate, materials."
        ),
        "keywords": ["CSI 300", "sector rotation", "defensive", "P/E", "valuation", "沪深300", "板块轮动", "估值"],
    },
    {
        "id": "mock-doc-007",
        "title": "China Healthcare Sector — Aging Population Tailwind",
        "source": "CICC Research",
        "date": "2026-06-25",
        "snippet": (
            "China's 60+ population reached 310 million (22% of total) in 2025 and is "
            "projected to reach 400 million by 2035. Healthcare expenditure as % of GDP "
            "rose to 7.2%. Innovative drug approvals (NDAs) hit a record 48 in 2025, "
            "with 12 receiving FDA breakthrough therapy designation. Medical device "
            "localization rate reached 45% in high-end imaging. TCM sector benefiting "
            "from policy tailwind — national TCM promotion plan launched March 2026."
        ),
        "keywords": ["healthcare", "医药", "pharma", "aging", "老龄化", "medical device", "TCM", "中药"],
    },
    {
        "id": "mock-doc-008",
        "title": "AI in Wealth Management: 2026 Landscape",
        "source": "McKinsey & Company",
        "date": "2026-05-22",
        "snippet": (
            "AI-powered wealth management platforms now manage $8.2T in AUM globally (up from "
            "$6T projected for 2027 — the estimate was conservative). Key trends: (1) LLM-based "
            "hyper-personalization achieving 35% higher client engagement vs traditional robos; "
            "(2) Multi-agent architectures enabling complex planning (tax, estate, retirement in "
            "one conversation); (3) Compliance copilots reducing manual review costs by 70%. "
            "Chinese fintech leads in AI adoption rate at 82% vs global 58%."
        ),
        "keywords": ["fintech", "AI", "wealth management", "金融科技", "智能投顾", "robo-advisor", "LLM"],
    },
    # ═══ Investor Education ═══
    {
        "id": "mock-doc-009",
        "title": "Guide: Understanding Market Volatility",
        "source": "Shanghai Stock Exchange Investor Education",
        "date": "2026-05-20",
        "snippet": (
            "Market corrections of 10–20% occur on average every 2–3 years in the A-share "
            "market. Historical data shows that investors who maintained their positions "
            "through corrections recovered losses within 12–18 months on average. "
            "Diversification across 3+ sectors reduces portfolio volatility by 30-40%. "
            "Dollar-cost averaging reduces timing risk significantly for retail investors "
            "with 3+ year investment horizons."
        ),
        "keywords": ["volatility", "correction", "investor education", "diversification", "risk", "定投", "波动"],
    },
    {
        "id": "mock-doc-010",
        "title": "Pillar 3 Private Pension — Two Year Review",
        "source": "National Financial Regulatory Administration (NFRA)",
        "date": "2026-06-15",
        "snippet": (
            "China's private pension (Pillar 3) enrolled 85M+ participants in its second year. "
            "Total contributions reached ¥95B, with average annual contribution rising to "
            "¥8,500 per participant. Target-date pension FOFs delivered 3.1% average return. "
            "Contribution cap raised to ¥18,000 in January 2026. Policy expansion to include "
            "commercial insurance products and index funds broadened investment choices."
        ),
        "keywords": ["pension", "养老金", "Pillar 3", "第三支柱", "retirement", "养老", "FOF"],
    },
    # ═══ Fund Flows ═══
    {
        "id": "mock-doc-011",
        "title": "Q2 2026 Fund Flow Analysis — A-Share Market",
        "source": "China Merchants Securities",
        "date": "2026-07-16",
        "snippet": (
            "Northbound net inflows totaled ¥28.7 billion in Q2 2026, concentrated in "
            "consumer staples and industrial automation. Domestic mutual fund subscription "
            "volumes declined 12% QoQ. ETF inflows hit a record ¥156 billion, dominated "
            "by CSI 300 and STAR 50 index products. Retail investor sentiment index "
            "registered 42/100 (cautious zone). Bond funds continue to attract the "
            "largest share of new subscriptions (55% of total)."
        ),
        "keywords": ["fund flow", "northbound", "ETF", "retail sentiment", "mutual fund", "北向资金", "资金流向"],
    },
    # ═══ Real Estate & Infrastructure ═══
    {
        "id": "mock-doc-012",
        "title": "Real Estate Policy Easing — 2026 Impact Assessment",
        "source": "China Index Academy",
        "date": "2026-07-05",
        "snippet": (
            "Following the September 2024 policy package, Tier-1 city transaction volumes "
            "stabilized with Shanghai and Shenzhen seeing 25-35% MoM increases in H1 2026. "
            "However, developers' financing pressure remains acute with ¥210B in bond maturities "
            "due in H2 2026. Property sector weighting in CSI 300 fell further to 4.5% from "
            "9.2% in 2023. White-list project financing reached ¥2.8T disbursed. Recovery "
            "is K-shaped — state-owned developers gaining share while private developers "
            "continue to deleverage."
        ),
        "keywords": ["real estate", "房地产", "policy", "政策", "mortgage", "房贷", "developer", "开发商"],
    },
    # ═══ ESG / Green Finance ═══
    {
        "id": "mock-doc-013",
        "title": "Green Finance & EU CBAM — Impact on Chinese Exporters",
        "source": "Industrial Bank Green Finance Research",
        "date": "2026-06-20",
        "snippet": (
            "EU CBAM entered full implementation in January 2026. Chinese steel and aluminum "
            "exporters face additional costs of 5-10% of export value. Carbon trading price "
            "on China's national ETS rose to ¥88-95/ton CO2 as free allowances phase down. "
            "Green bond issuance reached ¥1.5T in H1 2026 (+28% YoY). Transition finance "
            "products (SLB, transition bonds) grew 150% YoY. Key beneficiary sectors: carbon "
            "verification agencies, green certification, low-carbon steel/aluminum producers."
        ),
        "keywords": ["green finance", "绿色金融", "CBAM", "carbon", "碳交易", "ESG", "sustainable", "低碳"],
    },
    # ═══ International / Cross-Border ═══
    {
        "id": "mock-doc-014",
        "title": "A-H Share Premium Analysis — Cross-Border Arbitrage",
        "source": "Goldman Sachs China Strategy",
        "date": "2026-07-01",
        "snippet": (
            "The Hang Seng AH Premium Index hovered at 140-148 in Q2 2026, meaning A-shares "
            "trade at a 40-48% premium to H-share counterparts. Widest premium sectors: "
            "financials (50%), materials (45%), industrials (42%). Narrowest: consumer "
            "discretionary (16%), healthcare (20%). Southbound connect net inflows reached "
            "¥480B YTD, concentrated in high-dividend SOEs: China Mobile, CNOOC, ICBC."
        ),
        "keywords": ["AH premium", "A股H股", "arbitrage", "套利", "southbound", "港股通", "cross-border"],
    },
    {
        "id": "mock-doc-015",
        "title": "Fed Policy & Global EM Implications — July 2026",
        "source": "IMF / World Bank Global Economic Prospects",
        "date": "2026-07-05",
        "snippet": (
            "The Federal Reserve held rates at 3.25-3.50% in July 2026, with markets pricing "
            "one 25bp cut by December. US 10Y yield at 3.85%. Dollar index (DXY) at 100.2, "
            "down 8% from 2025 highs. This has eased pressure on EM currencies — CNH strengthened "
            "to 7.08/USD. Global EM portfolio inflows reached $85B in H1 2026, with China "
            "receiving the largest share ($32B). IMF projects China GDP growth of 4.8% in 2026, "
            "driven by consumption recovery and manufacturing export strength."
        ),
        "keywords": ["Fed", "美联储", "interest rate", "dollar", "EM", "CNH", "人民币", "GDP", "IMF"],
    },
    # ═══ Risk Management ═══
    {
        "id": "mock-doc-016",
        "title": "Portfolio Risk Management in Multi-Asset Context",
        "source": "CFA Institute Research Foundation",
        "date": "2026-04-10",
        "snippet": (
            "Modern portfolio risk management requires multi-dimensional analysis beyond "
            "traditional mean-variance optimization. Key frameworks: (1) Stress testing — "
            "scenario analysis for tail risks (geopolitical, climate, regulatory); "
            "(2) Factor decomposition — understanding exposure to value, momentum, quality, "
            "and low-volatility factors; (3) Liquidity risk — market depth analysis for "
            "position sizing. For Chinese portfolios, currency risk (CNH/USD) and policy "
            "risk (regulatory shifts) are the two most under-hedged exposures."
        ),
        "keywords": ["risk management", "风险管理", "portfolio", "stress testing", "factor", "VaR", "liquidity"],
    },
    {
        "id": "mock-doc-017",
        "title": "Understanding Sharpe Ratio and Portfolio Evaluation Metrics",
        "source": "Shanghai Advanced Institute of Finance (SAIF)",
        "date": "2026-03-15",
        "snippet": (
            "The Sharpe ratio measures risk-adjusted return as (Rp - Rf) / σp. A Sharpe ratio "
            "above 1.0 is generally considered good, above 2.0 excellent. However, it has "
            "limitations: (1) assumes normal distribution of returns — problematic for assets "
            "with fat tails; (2) does not distinguish upside from downside volatility — "
            "Sortino ratio addresses this; (3) sensitive to the chosen risk-free rate. "
            "For Chinese portfolios, the CSI 300 5-year Sharpe ratio is approximately 0.42, "
            "while a balanced 60/40 stock/bond portfolio achieved 0.85 over the same period."
        ),
        "keywords": ["Sharpe", "夏普比率", "Sortino", "risk-adjusted", "portfolio", "风险调整", "evaluation"],
    },
    # ═══ Quantitative Trading ═══
    {
        "id": "mock-doc-018",
        "title": "Quantitative Trading Regulatory Framework — 2026 Update",
        "source": "CSRC / AMAC Joint Notice",
        "date": "2026-02-28",
        "snippet": (
            "Updated quant trading reporting requirements effective 2026: (1) Order-to-trade "
            "ratio capped at 250:1 per account per day (tightened from 300:1); (2) Minimum "
            "resting time reduced to 30ms for market orders with exchange approval; "
            "(3) Algorithmic trading strategies must pass pre-deployment risk assessment; "
            "(4) AI/ML-driven strategies subject to additional model interpretability "
            "requirements. Non-compliance penalties include trading suspension and fines."
        ),
        "keywords": ["quantitative trading", "量化交易", "regulation", "监管", "programmatic", "程序化交易", "algorithm"],
    },
    # ═══ Commodities ═══
    {
        "id": "mock-doc-019",
        "title": "Gold & Commodity Outlook — H2 2026",
        "source": "World Gold Council / Shanghai Gold Exchange",
        "date": "2026-07-10",
        "snippet": (
            "Gold prices reached $2,580/oz in July 2026 (+18% YTD), driven by central bank "
            "buying (PBOC added 180 tons in H1 2026), geopolitical uncertainty, and real "
            "yield compression. Copper at $9,800/ton, supported by green transition demand "
            "and constrained supply from Chile/Peru. Iron ore declined to $92/ton as Chinese "
            "steel production plateaued. Lithium carbonate stabilized at ¥98,000/ton. "
            "Shanghai crude oil futures (SC) at ¥585/barrel, tracking Brent at $78/barrel."
        ),
        "keywords": ["gold", "黄金", "commodity", "大宗商品", "copper", "铜", "lithium", "iron ore", "crude oil"],
    },
    # ═══ US-China Relations ═══
    {
        "id": "mock-doc-020",
        "title": "US-China Technology Competition — Mid-2026 Status",
        "source": "Rhodium Group / CSIS",
        "date": "2026-07-01",
        "snippet": (
            "The technology competition has evolved into a 'parallel stack' model: separate "
            "AI ecosystems, semiconductor supply chains, and cloud infrastructure stacks. "
            "Key developments: (1) DeepSeek and other Chinese LLMs achieving GPT-4-class "
            "performance with 30-50% less compute; (2) Chinese semiconductor tool localization "
            "at 32% vs 7% in 2018 — still dependent on ASML for advanced lithography; "
            "(3) Cross-border VC into Chinese AI startups down 85% from 2021 peak due to "
            "outbound investment screening; (4) Collaborative spaces remain in climate tech "
            "and basic research where decoupling is impractical."
        ),
        "keywords": ["US-China", "中美", "technology", "decoupling", "AI", "semiconductor", "DeepSeek"],
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
    1. Dense pass  — semantic similarity via RAG module (or mocked hash-embedding)
    2. Sparse pass — BM25 keyword matching against title + keywords
    3. Merge       — weighted reciprocal rank fusion (WRF)
    4. Return top-k deduplicated snippets

    PHASE 6 UPGRADE: Now uses the real RAG pipeline (app.rag.retriever) when
    available, with graceful fallback to the legacy mock scorer.

    This returns FACTS AND CONTEXT only — NO advice generation.

    Args:
        query:  Natural-language search query.
        top_k:  Number of top documents to return (default 3).

    Returns:
        dict with keys:
          - status:   "ok"
          - results:  list of {title, source, date, snippet, relevance_score}
          - method:   "hybrid (dense + sparse)" or "hybrid (RAG pipeline)"
    """
    # ── Try the new RAG pipeline first ──
    try:
        from app.rag.retriever import get_retriever
        retriever = get_retriever()
        rag_results = retriever.retrieve(query, top_k=top_k)

        if rag_results:
            results = []
            for r in rag_results:
                results.append({
                    "title": r.get("title", ""),
                    "source": r.get("source", ""),
                    "date": r.get("date", ""),
                    "snippet": r.get("snippet", ""),
                    "relevance_score": r.get("score", 0.0),
                    "category": r.get("category", ""),
                    "keywords": r.get("keywords", []),
                })

            return {
                "status": "ok",
                "results": results,
                "method": "hybrid (RAG pipeline: dense embedding + sparse keyword fusion)",
                "query": query,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        logger.debug("[tools] RAG pipeline unavailable (%s), falling back to mock", exc)

    # ── Legacy fallback: mock dense + sparse scoring ──
    query_terms: List[str] = re.findall(r"[一-鿿]+|[a-zA-Z]+", query)

    scored: List[Dict[str, Any]] = []
    for doc in _MOCK_DOCUMENTS:
        d_score = _dense_score(doc["snippet"], query)
        s_score = _sparse_score(doc.get("keywords", []), query_terms)
        combined = 0.6 * d_score + 0.4 * s_score
        scored.append({
            "title": doc["title"],
            "source": doc["source"],
            "date": doc["date"],
            "snippet": doc["snippet"],
            "relevance_score": round(combined, 4),
        })

    scored.sort(key=lambda d: d["relevance_score"], reverse=True)
    top = scored[:top_k]

    return {
        "status": "ok",
        "results": top,
        "method": "hybrid (dense + sparse mock)",
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
    """Search the web for real-time financial information (sync wrapper).

    This is a synchronous wrapper for use in sync contexts.
    For async contexts (e.g., agent nodes), use web_search_async() instead
    to avoid blocking the event loop.

    Args:
        query:      Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: title, url, snippet. Empty list on error.
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

        results = _parse_ddg_response(data, max_results)

        if results:
            logger.info("[tools] Web search: %d results for '%s'", len(results), query[:60])
        else:
            logger.info("[tools] Web search: no results for '%s'", query[:60])

    except ImportError:
        logger.debug("[tools] httpx not available for web search")
    except Exception as exc:
        logger.warning("[tools] Web search failed for '%s': %s", query[:60], exc)

    return results


async def web_search_async(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search the web for real-time financial information (async).

    Uses httpx.AsyncClient to avoid blocking the event loop.
    Safe to call from async agent nodes.

    Args:
        query:      Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: title, url, snippet. Empty list on error.
    """
    if not _WEB_SEARCH_ENABLED:
        logger.debug("[tools] Web search disabled via WEB_SEARCH_ENABLED env var")
        return []

    results: List[Dict[str, str]] = []

    try:
        import urllib.parse

        import httpx

        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

        async with httpx.AsyncClient(timeout=_WEB_SEARCH_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        results = _parse_ddg_response(data, max_results)

        if results:
            logger.info("[tools] Web search (async): %d results for '%s'", len(results), query[:60])
        else:
            logger.info("[tools] Web search (async): no results for '%s'", query[:60])

    except ImportError:
        logger.debug("[tools] httpx not available for async web search")
    except Exception as exc:
        logger.warning("[tools] Web search (async) failed for '%s': %s", query[:60], exc)

    return results


def _parse_ddg_response(data: dict, max_results: int) -> List[Dict[str, str]]:
    """Parse DuckDuckGo JSON response into structured results."""
    results: List[Dict[str, str]] = []

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
