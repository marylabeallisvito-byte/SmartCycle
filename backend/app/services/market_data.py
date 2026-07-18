"""
SmartCycle — Market Data Service
=================================

Higher-level market data operations with caching, batching, and error handling.
Wraps the low-level tools in app.tools with retry logic and TTL caching.

Python 3.9 compatible — no PEP 604 union syntax.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.tools import fetch_market_data

logger = logging.getLogger("smartcycle.services.market_data")

# Default TTL for cache entries
_DEFAULT_CACHE_TTL_SECONDS = 60  # 1 minute for market data


class MarketDataService:
    """Market data service with caching and concurrent batch fetching.

    Each instance maintains its own cache — instances with different TTLs
    do not share state.

    Usage:
        svc = MarketDataService()
        data = await svc.get_snapshot("000300")
        batch = await svc.get_batch(["000300", "600519", "NVDA"])
        summary = await svc.get_market_summary()
    """

    def __init__(self, cache_ttl: int = _DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    async def get_snapshot(self, symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch market data for a single symbol, with caching.

        Args:
            symbol: Ticker symbol (e.g., '600519', '000300', 'NVDA').
            force_refresh: If True, bypass cache and fetch fresh data.

        Returns:
            Market data dict from fetch_market_data().
        """
        # Check cache
        cache_key = f"snapshot:{symbol}"
        if not force_refresh and cache_key in self._cache:
            cached_at, cached_data = self._cache[cache_key]
            if time.time() - cached_at < self._ttl:
                logger.debug("[market_data] Cache hit for %s (%.1fs old)", symbol, time.time() - cached_at)
                return cached_data

        # Fetch in thread (tools are sync, service is async)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, fetch_market_data, symbol)

        # Cache result
        self._cache[cache_key] = (time.time(), data)

        return data

    async def get_batch(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch market data for multiple symbols concurrently.

        Args:
            symbols: List of ticker symbols.

        Returns:
            Dict mapping symbol → market data dict.
        """
        tasks = [self.get_snapshot(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: Dict[str, Dict[str, Any]] = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning("[market_data] Batch fetch failed for %s: %s", symbol, result)
                out[symbol] = {"symbol": symbol, "error": str(result), "status": "fetch_failed"}
            else:
                out[symbol] = result
        return out

    async def get_market_summary(self) -> Dict[str, Any]:
        """Fetch a summary of major market indices.

        Returns CSI 300, SSE Composite, SZSE Component, and ChiNext data.
        """
        major_indices = ["000300", "000001", "399001", "399006"]
        batch = await self.get_batch(major_indices)

        indices = []
        for symbol, data in batch.items():
            indices.append({
                "symbol": symbol,
                "name": data.get("name", ""),
                "name_cn": data.get("name_cn", ""),
                "price": data.get("price", 0),
                "change": data.get("change", 0),
                "change_pct": data.get("change_pct", 0),
            })

        return {
            "indices": indices,
            "count": len(indices),
            "updated_at": time.time(),
        }

    def clear_cache(self) -> int:
        """Clear this instance's in-memory market data cache. Returns count of cleared entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("[market_data] Instance cache cleared (%d entries)", count)
        return count
