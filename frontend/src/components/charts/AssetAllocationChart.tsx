"use client";

/* ============================================================
   SmartCycle — Asset Allocation Sunburst / Donut Chart

   Renders a premium ECharts sunburst or nested-ring chart
   showing portfolio allocation with neon-infused palette.

   Features:
     • Sunburst for hierarchical view (category → subcategory)
     • Falls back to donut for flat allocations
     • Dark Bloomberg-esque styling
     • Tooltip with CNY values and percentages
============================================================ */

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { PortfolioAllocation } from "@/lib/mockData";

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

interface Props {
  allocations: PortfolioAllocation[];
  totalValueYuan: number;
  clientName: string;
}

// ── Format CNY ──
const fmtCNY = (v: number): string => {
  if (v >= 1e8) return `¥${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `¥${(v / 1e4).toFixed(0)}万`;
  return `¥${v.toLocaleString()}`;
};

// ═══════════════════════════════════════════════════════════════
// Build ECharts sunburst data
// ═══════════════════════════════════════════════════════════════

function buildSunburstData(
  allocations: PortfolioAllocation[],
): Array<Record<string, unknown>> {
  const hasChildren = allocations.some((a) => a.children && a.children.length > 0);

  if (!hasChildren) {
    // Flat: use donut style
    return allocations.map((a) => ({
      name: `${a.categoryCn}\n${a.percentage}%`,
      value: a.percentage,
      itemStyle: {
        color: a.color,
        borderColor: "#0a0a14",
        borderWidth: 3,
      },
    }));
  }

  // Hierarchical: sunburst
  return allocations.map((a) => ({
    name: a.categoryCn,
    itemStyle: {
      color: a.color,
      borderColor: "#0a0a14",
      borderWidth: 2,
    },
    children: a.children
      ? a.children.map((child) => ({
          name: `${child.categoryCn}\n${child.percentage}%`,
          value: child.percentage,
          itemStyle: {
            color: child.color,
            borderColor: "#0a0a14",
            borderWidth: 2,
          },
        }))
      : [{ name: a.categoryCn, value: a.percentage }],
  }));
}

// ═══════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════

export default function AssetAllocationChart({
  allocations,
  totalValueYuan,
  clientName,
}: Props) {
  const hasHierarchy = allocations.some((a) => a.children && a.children.length > 0);

  const option = useMemo(() => {
    const seriesData = buildSunburstData(allocations);

    if (hasHierarchy) {
      // ── Sunburst ──
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item" as const,
          backgroundColor: "#141428",
          borderColor: "#1e2948",
          borderWidth: 1,
          textStyle: { color: "#e2e8f0", fontSize: 12, fontFamily: "Inter, Noto Sans SC, sans-serif" },
          formatter: (params: Record<string, unknown>) => {
            const pct = params.percent as number | undefined;
            return `<strong>${params.name}</strong><br/>占比: ${pct?.toFixed(1)}%`;
          },
        },
        series: [
          {
            type: "sunburst",
            data: seriesData,
            radius: ["18%", "85%"],
            center: ["50%", "52%"],
            nodeClick: false as const,
            sort: undefined,
            emphasis: {
              focus: "ancestor" as const,
              itemStyle: { shadowBlur: 20, shadowColor: "rgba(0,212,255,0.4)" },
            },
            label: {
              show: true,
              rotate: "radial" as const,
              color: "#e2e8f0",
              fontSize: 10,
              fontFamily: "Inter, Noto Sans SC, sans-serif",
              minAngle: 8,
            },
            itemStyle: {
              borderColor: "#0a0a14",
              borderWidth: 2,
            },
            levels: [
              {},
              { // Level 1: inner ring (top-level categories)
                r0: "18%", r: "48%",
                label: { fontSize: 11, fontWeight: 600, color: "#e2e8f0" },
                itemStyle: { borderWidth: 3 },
              },
              { // Level 2: outer ring (sub-categories)
                r0: "50%", r: "85%",
                label: { fontSize: 9, color: "#94a3b8" },
              },
            ],
          },
        ],
      };
    }

    // ── Donut (flat allocation) ──
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item" as const,
        backgroundColor: "#141428",
        borderColor: "#1e2948",
        borderWidth: 1,
        textStyle: { color: "#e2e8f0", fontSize: 12, fontFamily: "Inter, Noto Sans SC, sans-serif" },
        formatter: (params: Record<string, unknown>) => {
          const name = params.name as string;
          const value = params.value as number;
          const alloc = allocations.find((a) => name.startsWith(a.categoryCn));
          const cnyVal = alloc?.valueYuan ?? 0;
          return `<strong>${name}</strong><br/>${fmtCNY(cnyVal)}<br/>占比: ${value}%`;
        },
      },
      legend: {
        bottom: 0,
        textStyle: { color: "#94a3b8", fontSize: 11, fontFamily: "Inter, Noto Sans SC, sans-serif" },
        itemGap: 12,
        itemWidth: 8,
        itemHeight: 8,
        icon: "roundRect" as const,
      },
      series: [
        {
          name: "Asset Allocation",
          type: "pie",
          radius: ["55%", "82%"],
          center: ["50%", "46%"],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: "#0a0a14",
            borderWidth: 3,
          },
          label: {
            show: true,
            position: "outside" as const,
            color: "#94a3b8",
            fontSize: 10,
            fontFamily: "Inter, Noto Sans SC, sans-serif",
            formatter: "{b}\n{d}%",
          },
          emphasis: {
            label: { fontSize: 14, fontWeight: "bold", color: "#e2e8f0" },
            scaleSize: 8,
            itemStyle: { shadowBlur: 20, shadowColor: "rgba(0,212,255,0.4)" },
          },
          data: seriesData,
        },
      ],
      graphic: {
        type: "text",
        left: "center",
        top: "42%",
        style: {
          text: `总资产\n${fmtCNY(totalValueYuan)}`,
          textAlign: "center",
          fill: "#e2e8f0",
          fontSize: 13,
          fontWeight: 600,
          fontFamily: "Inter, Noto Sans SC, sans-serif",
          lineHeight: 20,
        },
      },
    };
  }, [allocations, totalValueYuan, hasHierarchy]);

  return (
    <div className="surface-card p-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[#e2e8f0]">
            资产配置 · Asset Allocation
          </h3>
          <p className="text-2xs text-[#64748b]">{clientName}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-2xs text-[#64748b]">
            {hasHierarchy ? "Sunburst" : "Donut"}
          </span>
          <span className="status-dot status-dot-active" />
        </div>
      </div>

      {/* Chart */}
      <ReactECharts
        option={option}
        style={{ height: 320, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />

      {/* Quick stats */}
      <div className="mt-2 grid grid-cols-3 gap-2">
        {allocations.slice(0, 3).map((a) => (
          <div
            key={a.category}
            className="flex items-center gap-2 rounded-lg bg-[#0a0a14] px-3 py-2"
          >
            <span
              className="h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: a.color }}
            />
            <div>
              <p className="text-2xs text-[#64748b]">{a.categoryCn}</p>
              <p className="text-xs font-semibold font-mono text-[#e2e8f0]">
                {a.percentage}%
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
