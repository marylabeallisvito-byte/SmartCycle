"use client";

/* ============================================================
   SmartCycle — useChat Hook (Phase 7 Enhanced)
   ============================================================

   Features:
     • Real HTTP calls to Tornado backend (POST /api/v1/chat)
     • AbortController for cancellation
     • Pipeline progress tracking (per-node status)
     • Configurable timeout
     • Error handling with user-friendly messages
============================================================ */

import { useCallback, useRef, useState } from "react";
import { chatWithAgent } from "./api";
import type { ClientProfile } from "./mockData";
import type { ChatMessage, AgentTrace } from "@/types";

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

/** Which pipeline node is currently executing. */
export type PipelineStage =
  | "idle"
  | "router"
  | "researcher"
  | "copilot"
  | "compliance"
  | "done"
  | "error"
  | "cancelled";

/** Progress info emitted during pipeline execution. */
export interface PipelineProgress {
  stage: PipelineStage;
  detail: string;
  startedAt?: number;
}

// ═══════════════════════════════════════════════════════════════
// Default timeout (ms) — LLM calls may take 20-60s
// ═══════════════════════════════════════════════════════════════

const DEFAULT_TIMEOUT_MS = 90_000; // 90 seconds

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
  const [progress, setProgress] = useState<PipelineProgress>({
    stage: "idle",
    detail: "",
  });

  // AbortController ref for cancellation
  const abortRef = useRef<AbortController | null>(null);

  /** Cancel the currently running request. */
  const cancelRequest = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setIsLoading(false);
      setProgress({ stage: "cancelled", detail: "Request cancelled by user" });
    }
  }, []);

  const sendMessage = useCallback(
    async (text: string): Promise<ChatMessage> => {
      // Cancel any in-flight request
      if (abortRef.current) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;

      setIsLoading(true);
      setError(null);
      setProgress({ stage: "router", detail: "Classifying query...", startedAt: Date.now() });

      // ── Timeout ──
      const timeoutId = setTimeout(() => {
        controller.abort();
      }, DEFAULT_TIMEOUT_MS);

      try {
        // ── Simulate pipeline progress ──
        // NOTE: These setTimeout-based progress updates are SIMULATED.
        // To wire to real server-side pipeline events:
        //   1. Connect to /ws/v1/chat WebSocket (see createReconnectingWebSocket in api.ts)
        //   2. Listen for 'stage_update' events: { stage, detail, timestamp }
        //   3. Replace these fixed timeouts with the WebSocket message handler.
        //   4. See docs/architecture.md §WebSocket for the event format.
        const progressTimer1 = setTimeout(
          () => setProgress({ stage: "researcher", detail: "Fetching market data & RAG context...", startedAt: Date.now() }),
          200,
        );
        const progressTimer2 = setTimeout(
          () => setProgress({ stage: "copilot", detail: "Generating empathetic response...", startedAt: Date.now() }),
          600,
        );
        const progressTimer3 = setTimeout(
          () => setProgress({ stage: "compliance", detail: "Screening for compliance...", startedAt: Date.now() }),
          1000,
        );

        // ── Call the real backend ──
        const response = await chatWithAgent(
          {
            query: text,
            client_profile: selectedClient
              ? toBackendProfile(selectedClient)
              : undefined,
          },
          controller.signal,
        );

        // Cleanup progress timers
        clearTimeout(progressTimer1);
        clearTimeout(progressTimer2);
        clearTimeout(progressTimer3);
        clearTimeout(timeoutId);

        // Check if cancelled during the request
        if (controller.signal.aborted) {
          return {
            id: `msg-${Date.now()}`,
            role: "assistant" as const,
            content: "⏹️ 请求已取消。",
            timestamp: new Date().toISOString(),
            compliancePassed: false,
          };
        }

        setProgress({ stage: "done", detail: "Complete", startedAt: Date.now() });

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
        clearTimeout(timeoutId);

        if (controller.signal.aborted) {
          setProgress({ stage: "cancelled", detail: "Request cancelled or timed out" });
          // Distinguish user cancel vs timeout
          const isTimeout = !abortRef.current;
          return {
            id: `msg-${Date.now()}`,
            role: "assistant" as const,
            content: isTimeout
              ? "⏰ 请求超时。系统处理时间较长，请简化问题后重试。\n\n> Request timed out. Please try a simpler query."
              : "⏹️ 请求已取消。",
            timestamp: new Date().toISOString(),
            compliancePassed: false,
          };
        }

        const message =
          err instanceof Error ? err.message : "Unknown error";
        setError(message);
        setProgress({ stage: "error", detail: message });

        console.error("[useChat] Pipeline error:", err);
        return {
          id: `msg-${Date.now()}`,
          role: "assistant" as const,
          content: `⚠️ 抱歉，系统处理您的请求时遇到错误。\n\n> ${message}\n\n请确认后端服务已启动（http://localhost:8000），然后重试。`,
          timestamp: new Date().toISOString(),
          compliancePassed: false,
        };
      } finally {
        clearTimeout(timeoutId);
        abortRef.current = null;
        setIsLoading(false);
      }
    },
    [selectedClient],
  );

  /** Reset the error state (e.g. after displaying a toast). */
  const clearError = useCallback(() => {
    setError(null);
    setProgress({ stage: "idle", detail: "" });
  }, []);

  return { sendMessage, cancelRequest, isLoading, error, progress, clearError };
}
