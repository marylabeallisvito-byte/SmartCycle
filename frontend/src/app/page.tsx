"use client";

/* ============================================================
   SmartCycle — Advisor Copilot Master Dashboard
   ============================================================

   Three-column Bloomberg-esque layout:
     • Left Sidebar (280px):   Client list, quick stats, nav
     • Center Panel (flex-1):  AI Copilot ChatInterface
     • Right Panel (400px):    Client3DProfile + AssetAllocationChart

   All interactive — strictly client-rendered.
============================================================ */

import { useCallback, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  ChevronRight,
  Gauge,
  Layers,
  LogOut,
  Search,
  Settings,
  Users,
  Zap,
} from "lucide-react";

import ChatInterface from "@/components/ChatInterface";
import Client3DProfile from "@/components/Client3DProfile";
import MarketTicker from "@/components/MarketTicker";
import AssetAllocationChart from "@/components/charts/AssetAllocationChart";

import {
  MOCK_CLIENTS,
  MOCK_ALLOCATIONS,
  WELCOME_MESSAGE,
  type ChatMessage,
} from "@/lib/mockData";
import { useChat } from "@/lib/useChat";

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════

function fmtCNY(v: number): string {
  if (v >= 1e8) return `¥${(v / 1e8).toFixed(1)}亿`;
  if (v >= 1e4) return `¥${(v / 1e4).toFixed(0)}万`;
  return `¥${v.toLocaleString()}`;
}

function riskBadge(risk: string): { label: string; color: string; bg: string } {
  switch (risk) {
    case "conservative": return { label: "保守", color: "#10b981", bg: "bg-[#10b981]/10" };
    case "moderate": return { label: "稳健", color: "#8b5cf6", bg: "bg-[#8b5cf6]/10" };
    case "aggressive": return { label: "进取", color: "#f59e0b", bg: "bg-[#f59e0b]/10" };
    default: return { label: risk, color: "#94a3b8", bg: "bg-[#94a3b8]/10" };
  }
}

function pnlColor(pct: number): string {
  if (pct > 0) return "text-[#10b981]";
  if (pct < 0) return "text-[#ef4444]";
  return "text-[#94a3b8]";
}

// ═══════════════════════════════════════════════════════════════
// Page Component
// ═══════════════════════════════════════════════════════════════

export default function DashboardPage() {
  const [selectedClientId, setSelectedClientId] = useState<string>("c-001");
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Compute total AUM from mock clients
  const totalAum = useMemo(
    () => MOCK_CLIENTS.reduce((sum, c) => sum + c.aumYuan, 0),
    [],
  );

  // Filter clients by search query
  const filteredClients = useMemo(() => {
    if (!searchQuery.trim()) return MOCK_CLIENTS;
    const q = searchQuery.toLowerCase();
    return MOCK_CLIENTS.filter(
      (c) =>
        c.nameCn.includes(q) ||
        c.name.toLowerCase().includes(q) ||
        c.id.includes(q),
    );
  }, [searchQuery]);

  const selectedClient =
    filteredClients.find((c) => c.id === selectedClientId) ?? filteredClients[0];
  const allocations = selectedClient
    ? (MOCK_ALLOCATIONS[selectedClient.id] ?? [])
    : [];

  // ── Real API wiring (replaces Phase 3 mock) ──
  const { sendMessage, cancelRequest, isLoading, progress } = useChat(selectedClient);

  const handleSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: "user",
        content: text,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      const aiMsg = await sendMessage(text);
      setMessages((prev) => [...prev, aiMsg]);
    },
    [sendMessage],
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#06060c]">
      {/* ═══════════════════════════════════════════════════════
          LEFT SIDEBAR
          ═══════════════════════════════════════════════════════ */}
      <aside
        className={`flex shrink-0 flex-col border-r border-[#1e2948] bg-[#0a0a14] transition-all duration-300 ${
          sidebarCollapsed ? "w-[60px]" : "w-[280px]"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 border-b border-[#1e2948] px-4 py-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#8b5cf6]">
            <Zap className="h-4 w-4 text-white" />
          </div>
          {!sidebarCollapsed && (
            <div>
              <h1 className="text-sm font-bold tracking-tight text-[#e2e8f0]">
                SmartCycle
              </h1>
              <p className="text-2xs text-[#64748b]">金仕达·智循</p>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="ml-auto rounded-lg p-1 text-[#64748b] hover:bg-[#141428] hover:text-[#e2e8f0] transition-colors"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <ChevronRight
              className={`h-4 w-4 transition-transform ${sidebarCollapsed ? "rotate-180" : ""}`}
            />
          </button>
        </div>

        {/* Quick Stats */}
        {!sidebarCollapsed && (
          <div className="border-b border-[#1e2948] px-4 py-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-[#0f0f1e] p-2.5">
                <p className="text-2xs text-[#64748b]">AUM</p>
                <p className="text-sm font-semibold font-mono text-[#e2e8f0]">{fmtCNY(totalAum)}</p>
              </div>
              <div className="rounded-lg bg-[#0f0f1e] p-2.5">
                <p className="text-2xs text-[#64748b]">Clients</p>
                <p className="text-sm font-semibold font-mono text-[#e2e8f0]">{filteredClients.length}</p>
              </div>
            </div>
          </div>
        )}

        {/* Nav Links */}
        {!sidebarCollapsed && (
          <nav className="px-3 py-2 space-y-0.5">
            {[
              { icon: Bot, label: "AI Copilot", active: true },
              { icon: BarChart3, label: "Market Monitor", disabled: true },
              { icon: Layers, label: "Portfolios", disabled: true },
              { icon: Users, label: "Client Management", disabled: true },
              { icon: Gauge, label: "Risk Analytics", disabled: true },
            ].map(({ icon: Icon, label, active, disabled }) => (
              <button
                key={label}
                disabled={disabled}
                title={disabled ? `${label} — Coming in Phase 8` : label}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-[#00d4ff]/10 text-[#00d4ff]"
                    : disabled
                    ? "text-[#475569] cursor-not-allowed"
                    : "text-[#94a3b8] hover:bg-[#141428] hover:text-[#e2e8f0]"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>
        )}

        {/* Client List Header */}
        {!sidebarCollapsed && (
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">
              客户列表 · Clients
            </p>
            <span className="text-2xs font-mono text-[#64748b]">{MOCK_CLIENTS.length}</span>
          </div>
        )}

        {/* Client List */}
        <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-1">
          {filteredClients.map((client) => {
            const badge = riskBadge(client.riskTolerance);
            const isActive = client.id === selectedClientId;
            return (
              <button
                key={client.id}
                onClick={() => setSelectedClientId(client.id)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all ${
                  isActive
                    ? "bg-[#1a1a33] border border-[#263355] neon-ring"
                    : "hover:bg-[#0f0f1e] border border-transparent"
                }`}
              >
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${client.avatarGradient} text-xs font-bold text-white`}
                >
                  {client.nameCn[0]}
                </div>
                {!sidebarCollapsed && (
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-[#e2e8f0]">
                        {client.nameCn}
                      </span>
                      <span
                        className="shrink-0 rounded-full px-1.5 py-0.5 text-2xs font-medium"
                        style={{
                          color: badge.color,
                          backgroundColor: badge.color + "18",
                        }}
                      >
                        {badge.label}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <span className="text-xs font-mono text-[#94a3b8]">
                        {fmtCNY(client.portfolioValueYuan)}
                      </span>
                      <span className={`text-2xs font-mono font-medium ${pnlColor(client.ytdReturnPct)}`}>
                        {client.ytdReturnPct > 0 ? "+" : ""}{client.ytdReturnPct}% YTD
                      </span>
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom controls */}
        <div className="border-t border-[#1e2948] px-3 py-3 space-y-1">
          <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-[#94a3b8] hover:bg-[#141428] hover:text-[#e2e8f0] transition-colors">
            <Settings className="h-4 w-4" />
            {!sidebarCollapsed && "Settings"}
          </button>
          <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-[#64748b] hover:bg-[#141428] hover:text-[#ef4444] transition-colors">
            <LogOut className="h-4 w-4" />
            {!sidebarCollapsed && "Logout"}
          </button>
        </div>
      </aside>

      {/* ═══════════════════════════════════════════════════════
          CENTER — ChatInterface
          ═══════════════════════════════════════════════════════ */}
      <main className="flex flex-1 flex-col min-w-0 border-r border-[#1e2948]">
        {/* Mini top bar */}
        <div className="flex items-center gap-3 border-b border-[#1e2948] bg-[#0a0a14] px-5 py-2.5">
          <Search className="h-3.5 w-3.5 text-[#64748b]" aria-hidden="true" />
          <input
            placeholder="Search clients, tickers, or topics..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none"
            aria-label="Search clients, tickers, or topics"
          />
          <div className="hidden items-center gap-3 text-xs text-[#64748b] lg:flex">
            <MarketTicker />
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 min-h-0">
          <ChatInterface
            messages={messages}
            onSend={handleSend}
            isLoading={isLoading}
            selectedClientName={selectedClient?.nameCn}
            onCancel={cancelRequest}
            progress={progress}
          />
        </div>
      </main>

      {/* ═══════════════════════════════════════════════════════
          RIGHT PANEL — Client Insights
          ═══════════════════════════════════════════════════════ */}
      <aside className="w-[400px] shrink-0 overflow-y-auto bg-[#0a0a14] p-4 space-y-4">
        {!selectedClient ? (
          <div className="surface-card p-8 text-center">
            <Users className="mx-auto h-8 w-8 text-[#475569] mb-3" />
            <p className="text-sm text-[#64748b]">No client selected</p>
            <p className="text-2xs text-[#475569] mt-1">Select a client from the sidebar to view their profile.</p>
          </div>
        ) : (
          <>
        {/* Client header card */}
        <div className="surface-card p-4">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${selectedClient.avatarGradient} text-lg font-bold text-white`}
            >
              {selectedClient.nameCn[0]}
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-[#e2e8f0]">{selectedClient.nameCn}</h2>
              <p className="text-xs text-[#64748b]">{selectedClient.name}</p>
            </div>
            <span
              className="ml-auto shrink-0 rounded-full px-2 py-0.5 text-2xs font-medium"
              style={{
                color: riskBadge(selectedClient.riskTolerance).color,
                backgroundColor: riskBadge(selectedClient.riskTolerance).color + "18",
              }}
            >
              {riskBadge(selectedClient.riskTolerance).label}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <StatBlock label="Portfolio" value={fmtCNY(selectedClient.portfolioValueYuan)} />
            <StatBlock label="AUM" value={fmtCNY(selectedClient.aumYuan)} />
            <StatBlock
              label="YTD Return"
              value={`${selectedClient.ytdReturnPct > 0 ? "+" : ""}${selectedClient.ytdReturnPct}%`}
              accent={selectedClient.ytdReturnPct >= 0 ? "text-[#10b981]" : "text-[#ef4444]"}
            />
          </div>
        </div>

        {/* 3D Client Profile */}
        <Client3DProfile
          riskTolerance={selectedClient.riskTolerance}
          anxietyLevel={selectedClient.anxietyLevel}
          clientName={selectedClient.nameCn}
        />

        {/* Asset Allocation Chart */}
        <AssetAllocationChart
          allocations={allocations}
          totalValueYuan={selectedClient.portfolioValueYuan}
          clientName={selectedClient.nameCn}
        />

        {/* Quick Facts */}
        <div className="surface-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-[#e2e8f0]">
            客户画像速览 · Quick Facts
          </h3>
          <div className="space-y-2.5">
            {[
              {
                label: "Age",
                value: `${selectedClient.age} years · ${selectedClient.age}岁`,
              },
              {
                label: "Knowledge",
                value:
                  selectedClient.knowledgeLevel === "beginner"
                    ? "初级 · Beginner"
                    : selectedClient.knowledgeLevel === "intermediate"
                    ? "中级 · Intermediate"
                    : "高级 · Advanced",
              },
              {
                label: "Horizon",
                value:
                  selectedClient.investmentHorizon === "short"
                    ? "短期 · Short"
                    : selectedClient.investmentHorizon === "medium"
                    ? "中期 · Medium"
                    : "长期 · Long",
              },
              {
                label: "Anxiety",
                value:
                  selectedClient.anxietyLevel === "low"
                    ? "冷静 · Calm"
                    : selectedClient.anxietyLevel === "medium"
                    ? "关注 · Attentive"
                    : "焦虑 · Anxious",
              },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="flex items-center justify-between rounded-lg bg-[#0f0f1e] px-3 py-2"
              >
                <span className="text-xs text-[#64748b]">{label}</span>
                <span className="text-xs font-medium text-[#e2e8f0]">{value}</span>
              </div>
            ))}
          </div>
        </div>
          </>
        )}
      </aside>
    </div>
  );
}

/* ── Tiny stat block ── */

function StatBlock({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-lg bg-[#0f0f1e] p-2 text-center">
      <p className="text-2xs text-[#64748b]">{label}</p>
      <p className={`text-xs font-mono font-semibold ${accent ?? "text-[#e2e8f0]"}`}>
        {value}
      </p>
    </div>
  );
}
