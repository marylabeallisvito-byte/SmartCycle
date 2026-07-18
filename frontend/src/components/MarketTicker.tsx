"use client";

/* ============================================================
   SmartCycle — Market Ticker Bar
   ============================================================

   Real-time scrolling market index ticker.
   Fetches from GET /api/v1/market/summary with auto-refresh.
   Falls back to mock data when API is unreachable.
============================================================ */

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus, Loader2 } from "lucide-react";
import { marketSummary, type MarketIndexSummary } from "@/lib/api";

// ── Mock fallback data ──

const MOCK_INDICES: MarketIndexSummary[] = [
  { symbol: "000300", name: "CSI 300", name_cn: "沪深300", price: 3987.45, change: 23.15, change_pct: 0.58 },
  { symbol: "000001", name: "SSE Composite", name_cn: "上证综指", price: 3245.12, change: -10.08, change_pct: -0.31 },
  { symbol: "399001", name: "SZSE Component", name_cn: "深证成指", price: 10782.56, change: 45.32, change_pct: 0.42 },
  { symbol: "399006", name: "ChiNext", name_cn: "创业板指", price: 2156.78, change: -18.45, change_pct: -0.85 },
];

// ── Helpers ──

function pnlColor(pct: number): string {
  if (pct > 0) return "text-[#10b981]";
  if (pct < 0) return "text-[#ef4444]";
  return "text-[#94a3b8]";
}

function pnlIcon(pct: number) {
  if (pct > 0) return <TrendingUp className="h-3 w-3 text-[#10b981]" />;
  if (pct < 0) return <TrendingDown className="h-3 w-3 text-[#ef4444]" />;
  return <Minus className="h-3 w-3 text-[#94a3b8]" />;
}

// ── Component ──

export default function MarketTicker() {
  const [indices, setIndices] = useState<MarketIndexSummary[]>(MOCK_INDICES);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIndices = async () => {
    try {
      const data = await marketSummary();
      if (data.indices && data.indices.length > 0) {
        setIndices(data.indices);
        setError(null);
      }
    } catch {
      // Silently fall back to mock data
      setError("Using mock data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIndices();
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchIndices, 60_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-6 overflow-x-auto px-4 py-2">
      {loading && indices.length === 0 ? (
        <div className="flex items-center gap-2 text-xs text-[#64748b]">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading market data...
        </div>
      ) : (
        <>
          {indices.map((idx) => (
            <div
              key={idx.symbol}
              className="flex shrink-0 items-center gap-2 text-xs"
              title={`${idx.name_cn} (${idx.name})`}
            >
              <span className="font-medium text-[#e2e8f0]">{idx.name_cn}</span>
              <span className="font-mono text-[#e2e8f0] tabular-nums">
                {idx.price.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`flex items-center gap-0.5 font-mono tabular-nums ${pnlColor(idx.change_pct)}`}>
                {pnlIcon(idx.change_pct)}
                {idx.change_pct > 0 ? "+" : ""}
                {idx.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
          {error && (
            <span className="text-2xs text-[#64748b] italic ml-2">{error}</span>
          )}
        </>
      )}
    </div>
  );
}
