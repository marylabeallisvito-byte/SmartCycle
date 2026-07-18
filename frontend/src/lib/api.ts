import axios from "axios";
import type { AdvisorQuery, AIResponse } from "@/types";

/* ============================================================
   SmartCycle — API Client
   ============================================================

   Pre-configured Axios instance pointing at the FastAPI backend.
   All endpoints are typed with request/response interfaces.
============================================================ */

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 120000,  // 2 minutes — LLM calls may take 20-60s
  headers: { "Content-Type": "application/json" },
});

// TODO: Add interceptors for JWT auth, token refresh, error handling

// ═══════════════════════════════════════════════════════════════
// Typed API Functions
// ═══════════════════════════════════════════════════════════════

/**
 * Send a financial query through the full multi-agent pipeline.
 *
 * POST /api/v1/chat
 *
 * Pipeline: Router → Quantitative Researcher → Empathy Copilot → Compliance Gatekeeper
 *                                                                    ↓
 *                                                        [conditional loop-back on failure]
 */
export async function chatWithAgent(payload: AdvisorQuery): Promise<AIResponse> {
  const { data } = await apiClient.post<AIResponse>("/api/v1/chat", payload);
  return data;
}

/**
 * Check backend health.
 * GET /api/v1/health
 */
export async function healthCheck(): Promise<{
  status: string;
  version: string;
  phase: string;
}> {
  const { data } = await apiClient.get("/api/v1/health");
  return data;
}

/**
 * Get graph introspection info.
 * GET /api/v1/graph/info
 */
export async function graphInfo(): Promise<{
  framework: string;
  architecture: string;
  pipeline: string[];
  max_compliance_retries: number;
  nodes: string[];
}> {
  const { data } = await apiClient.get("/api/v1/graph/info");
  return data;
}
