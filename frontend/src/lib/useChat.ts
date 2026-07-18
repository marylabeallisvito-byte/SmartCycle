"use client";

/* ============================================================
   SmartCycle — useChat Hook
   ============================================================

   Replaces the Phase 3 mock simulateAIResponse() with real
   HTTP calls to the FastAPI backend (POST /api/v1/chat).

   Responsibilities:
     • Serialise the selected ClientProfile to snake_case
     • POST the AdvisorQuery to the backend
     • Map the AIResponse → ChatMessage (with AgentTrace)
     • Expose isLoading / error for the UI layer
============================================================ */

import { useCallback, useState } from "react";
import { chatWithAgent } from "./api";
import type { ClientProfile, ChatMessage, AgentTrace } from "./mockData";

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════

/**
 * Convert the frontend ClientProfile (camelCase, from mockData)
 * into the backend ClientProfile (snake_case, Pydantic).
 */
function toBackendProfile(client: ClientProfile) {
  return {
    risk_tolerance: client.riskTolerance,
    anxiety_level: client.anxietyLevel,
    investment_horizon: client.investmentHorizon,
    knowledge_level: client.knowledgeLevel,
    age_range: `${Math.floor(client.age / 10) * 10}-${Math.floor(client.age / 10) * 10 + 9}`,
    portfolio_value_yuan: client.portfolioValueYuan,
  };
}

/**
 * Normalize backend snake_case market_data entries to the camelCase
 * shape expected by ChatInterface's AgentTraceAccordion.
 *
 * Backend: { "000300": { name_cn: "沪深300", price: 3987.45, ... } }
 * Frontend expects: { "000300": { nameCn: "沪深300", price: 3987.45, ... } }
 */
function normalizeMarketData(
  raw: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!raw) return undefined;
  const out: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(raw)) {
    if (val && typeof val === "object" && !Array.isArray(val)) {
      const entry: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
        // Map snake_case keys to camelCase for the ChatInterface
        if (k === "name_cn") entry["nameCn"] = v;
        else if (k === "change_pct") entry["changePct"] = v;
        else if (k === "pe_ttm") entry["peTtm"] = v;
        else if (k === "dividend_yield") entry["dividendYield"] = v;
        else if (k === "avg_volume_30d") entry["avgVolume30d"] = v;
        else if (k === "market_cap_bn_cny") entry["marketCapBnCny"] = v;
        else if (k === "updated_utc") entry["updatedUtc"] = v;
        else entry[k] = v;
      }
      out[key] = entry;
    } else {
      out[key] = val;
    }
  }
  return out;
}

// ═══════════════════════════════════════════════════════════════
// Hook
// ═══════════════════════════════════════════════════════════════

export function useChat(selectedClient: ClientProfile | null) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string): Promise<ChatMessage> => {
      setIsLoading(true);
      setError(null);

      try {
        // ── Call the real backend ──
        const response = await chatWithAgent({
          query: text,
          client_profile: selectedClient
            ? toBackendProfile(selectedClient)
            : undefined,
        });

        // ── Build AgentTrace from backend response ──
        const rawData = response.raw_data || {};

        const agentTrace: AgentTrace = {
          queryCategory: response.query_category,
          rawData: {
            marketData: normalizeMarketData(
              rawData.market_data as Record<string, unknown> | undefined,
            ),
            ragContext:
              (rawData.rag_context as Array<{
                title: string;
                source: string;
                snippet: string;
              }>) ?? undefined,
          },
          draftResponse: response.draft_response,
          complianceFlags: (response.compliance_flags || []).map((f) => ({
            rule: f.rule,
            severity: f.severity,
            bannedPhrase: f.banned_phrase,
            suggestion: f.suggestion,
          })),
          revisionCount: response.revision_count,
        };

        // ── Build the chat message the UI expects ──
        return {
          id: `msg-${Date.now()}`,
          role: "assistant" as const,
          content: response.final_response,
          timestamp: response.timestamp || new Date().toISOString(),
          compliancePassed: response.compliance_passed,
          agentTrace,
        };
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Unknown error";
        setError(message);

        // Return a user-visible error message so the chat doesn't break
        console.error("[useChat] Pipeline error:", err);
        return {
          id: `msg-${Date.now()}`,
          role: "assistant" as const,
          content: `⚠️ 抱歉，系统处理您的请求时遇到错误。\n\n> ${message}\n\n请确认后端服务已启动（http://localhost:8000），然后重试。`,
          timestamp: new Date().toISOString(),
          compliancePassed: false,
        };
      } finally {
        setIsLoading(false);
      }
    },
    [selectedClient],
  );

  /** Reset the error state (e.g. after displaying a toast). */
  const clearError = useCallback(() => setError(null), []);

  return { sendMessage, isLoading, error, clearError };
}
