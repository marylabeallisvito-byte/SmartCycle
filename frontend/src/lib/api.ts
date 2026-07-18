import axios from "axios";
import type { AdvisorQuery, AIResponse } from "@/types";

/* ============================================================
   SmartCycle — API Client
   ============================================================

   Pre-configured Axios instance pointing at the Tornado backend.
   All endpoints are typed with request/response interfaces.
============================================================ */

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 120000,  // 2 minutes — LLM calls may take 20-60s
  headers: { "Content-Type": "application/json" },
});

// ═══════════════════════════════════════════════════════════════
// Auth Interceptor
// ═══════════════════════════════════════════════════════════════

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("smartcycle_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("smartcycle_token");
      }
    }
    return Promise.reject(error);
  },
);

// ═══════════════════════════════════════════════════════════════
// Auth
// ═══════════════════════════════════════════════════════════════

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    username: string;
    role: string;
  };
}

/** POST /api/v1/auth/login — get JWT token for demo user. */
export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/api/v1/auth/login", payload);
  if (typeof window !== "undefined") {
    localStorage.setItem("smartcycle_token", data.access_token);
  }
  return data;
}

/** Remove the stored token. */
export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("smartcycle_token");
  }
}

/** Get the current stored token (or null). */
export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("smartcycle_token");
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════
// Core Pipeline
// ═══════════════════════════════════════════════════════════════

/**
 * Send a financial query through the full multi-agent pipeline.
 * POST /api/v1/chat
 */
export async function chatWithAgent(
  payload: AdvisorQuery,
  signal?: AbortSignal,
): Promise<AIResponse> {
  const { data } = await apiClient.post<AIResponse>("/api/v1/chat", payload, { signal });
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
  endpoints: number;
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

// ═══════════════════════════════════════════════════════════════
// Copilot (B-end)
// ═══════════════════════════════════════════════════════════════

/** GET /api/v1/copilot — copilot service status. */
export async function copilotStatus(): Promise<{
  service: string;
  status: string;
  version: string;
  pipeline: string;
}> {
  const { data } = await apiClient.get("/api/v1/copilot");
  return data;
}

/** POST /api/v1/copilot/query — B-end advisor research query. */
export async function copilotQuery(payload: AdvisorQuery): Promise<AIResponse> {
  const { data } = await apiClient.post<AIResponse>("/api/v1/copilot/query", payload);
  return data;
}

// ═══════════════════════════════════════════════════════════════
// Companion (C-end)
// ═══════════════════════════════════════════════════════════════

/** GET /api/v1/companion — companion service status. */
export async function companionStatus(): Promise<{
  service: string;
  status: string;
  version: string;
}> {
  const { data } = await apiClient.get("/api/v1/companion");
  return data;
}

/** POST /api/v1/companion/chat — C-end retail investor chat. */
export async function companionChat(payload: AdvisorQuery): Promise<AIResponse> {
  const { data } = await apiClient.post<AIResponse>("/api/v1/companion/chat", payload);
  return data;
}

// ═══════════════════════════════════════════════════════════════
// Compliance-as-a-Service
// ═══════════════════════════════════════════════════════════════

export interface ComplianceCheckRequest {
  text: string;
  risk_tolerance?: string;
  check_banned_terms?: boolean;
  check_suitability?: boolean;
}

export interface ComplianceCheckResponse {
  passed: boolean;
  flags_count: number;
  flags: Array<{
    rule: string;
    severity: string;
    banned_phrase: string;
    suggestion: string;
  }>;
  risk_rating: string;
  text_length: number;
}

/** GET /api/v1/compliance — compliance service status. */
export async function complianceStatus(): Promise<{
  service: string;
  status: string;
  version: string;
  active_rules_count: number;
}> {
  const { data } = await apiClient.get("/api/v1/compliance");
  return data;
}

/** POST /api/v1/compliance/check — standalone compliance screening. */
export async function complianceCheck(
  payload: ComplianceCheckRequest,
): Promise<ComplianceCheckResponse> {
  const { data } = await apiClient.post<ComplianceCheckResponse>(
    "/api/v1/compliance/check",
    payload,
  );
  return data;
}

export interface ComplianceRule {
  pattern: string;
  severity: string;
  suggestion: string;
  category: string;
}

/** GET /api/v1/compliance/rules — list all active compliance rules. */
export async function complianceRules(): Promise<{
  total_rules: number;
  rules: ComplianceRule[];
  disclaimer: string;
}> {
  const { data } = await apiClient.get("/api/v1/compliance/rules");
  return data;
}

// ═══════════════════════════════════════════════════════════════
// Market Data
// ═══════════════════════════════════════════════════════════════

export interface MarketIndexSummary {
  symbol: string;
  name: string;
  name_cn: string;
  price: number;
  change: number;
  change_pct: number;
}

/** GET /api/v1/market/summary — major indices snapshot. */
export async function marketSummary(): Promise<{
  indices: MarketIndexSummary[];
  count: number;
}> {
  const { data } = await apiClient.get("/api/v1/market/summary");
  return data;
}

// ═══════════════════════════════════════════════════════════════
// Portfolio Analysis
// ═══════════════════════════════════════════════════════════════

export interface PortfolioAnalysisRequest {
  holdings: Array<{
    symbol: string;
    asset_class: string;
    market_value_yuan: number;
  }>;
  total_value?: number;
}

/** POST /api/v1/portfolio/analysis — portfolio risk/return analytics. */
export async function portfolioAnalysis(payload: PortfolioAnalysisRequest): Promise<{
  total_value: number;
  holdings_count: number;
  asset_classes_count: number;
  allocation: Array<{
    asset_class: string;
    value_yuan: number;
    percentage: number;
    count: number;
  }>;
  concentration: {
    top_holding_pct: number;
    diversified: boolean;
  };
}> {
  const { data } = await apiClient.post("/api/v1/portfolio/analysis", payload);
  return data;
}

// ═══════════════════════════════════════════════════════════════
// WebSocket
// ═══════════════════════════════════════════════════════════════

/**
 * Create a WebSocket connection for streaming chat.
 * WS /ws/v1/chat
 */
export function createChatWebSocket(): WebSocket {
  const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
  return new WebSocket(`${wsBase}/ws/v1/chat`);
}

/**
 * Create a WebSocket connection with automatic reconnection and heartbeat.
 *
 * Features:
 *   • Exponential backoff on disconnect (1s → 2s → 4s → ... → max 30s)
 *   • Heartbeat ping every 30s to detect dead connections
 *   • onMessage / onError / onStatusChange callbacks
 *   • Manual close via returned cleanup function
 */
export interface ReconnectingWebSocketOptions {
  onMessage?: (event: MessageEvent) => void;
  onError?: (event: Event) => void;
  onStatusChange?: (status: "connecting" | "connected" | "disconnected" | "reconnecting") => void;
  maxReconnectDelayMs?: number;
  heartbeatIntervalMs?: number;
}

export function createReconnectingWebSocket(
  options: ReconnectingWebSocketOptions = {},
): { close: () => void } {
  const {
    onMessage,
    onError,
    onStatusChange,
    maxReconnectDelayMs = 30_000,
    heartbeatIntervalMs = 30_000,
  } = options;

  const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
  const url = `${wsBase}/ws/v1/chat`;

  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectDelay = 1_000; // start at 1s
  let closed = false;

  function clearTimers() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
  }

  function startHeartbeat() {
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, heartbeatIntervalMs);
  }

  function connect() {
    if (closed || (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING))) {
      return;
    }

    onStatusChange?.("connecting");
    ws = new WebSocket(url);

    ws.onopen = () => {
      reconnectDelay = 1_000; // reset backoff on successful connection
      onStatusChange?.("connected");
      startHeartbeat();
    };

    ws.onmessage = (event: MessageEvent) => {
      // Ignore pong responses
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === "pong") return;
      } catch { /* not JSON, pass through */ }
      onMessage?.(event);
    };

    ws.onerror = (event: Event) => {
      onError?.(event);
    };

    ws.onclose = () => {
      onStatusChange?.("disconnected");
      if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }

      if (!closed) {
        onStatusChange?.("reconnecting");
        reconnectTimer = setTimeout(() => {
          reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelayMs);
          connect();
        }, reconnectDelay);
      }
    };
  }

  connect();

  return {
    close: () => {
      closed = true;
      clearTimers();
      reconnectDelay = 1_000;
      if (ws) {
        ws.onclose = null; // prevent reconnect trigger
        ws.close();
        ws = null;
      }
    },
  };
}
