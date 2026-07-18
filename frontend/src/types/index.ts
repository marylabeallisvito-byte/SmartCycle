// ============================================================
// SmartCycle — Shared TypeScript Type Definitions
// ============================================================
// Aligned with backend app/schema.py (Phase 2+)

// --- User ---
export interface User {
  id: string;
  email: string;
  name: string;
  role: "advisor" | "investor" | "admin";
  orgId?: string;
}

// --- Market Data ---
export interface MarketSummary {
  date: string;
  indices: IndexSnapshot[];
  sentiment: "bullish" | "bearish" | "neutral";
  aiBrief: string;
}

export interface IndexSnapshot {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
}

// --- Portfolio ---
export interface PortfolioAnalysis {
  totalValue: number;
  allocation: AssetAllocation[];
  riskScore: number;
  sharpeRatio?: number;
  aiCommentary: string;
}

export interface AssetAllocation {
  assetClass: string;
  percentage: number;
  value: number;
}

// --- Chat ---
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  complianceStatus?: "passed" | "modified" | "blocked";
}

// --- Compliance ---
export interface ComplianceReport {
  passed: boolean;
  flags: ComplianceFlag[];
  modifiedText?: string;
}

export interface ComplianceFlag {
  rule: string;
  severity: "low" | "medium" | "high" | "critical";
  description: string;
  suggestion: string;
}

// ═══════════════════════════════════════════════════════════════
// Backend API Types — aligned with backend/app/schema.py
// ═══════════════════════════════════════════════════════════════

/** Matches backend ClientProfile (snake_case for API transport). */
export interface BackendClientProfile {
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  anxiety_level: "low" | "medium" | "high";
  investment_horizon: "short" | "medium" | "long";
  knowledge_level: "beginner" | "intermediate" | "advanced";
  age_range?: string;
  portfolio_value_yuan?: number;
}

/** POST /api/v1/chat request body. */
export interface AdvisorQuery {
  query: string;
  client_profile?: BackendClientProfile;
  conversation_id?: string;
  metadata?: Record<string, unknown>;
}

/** One compliance flag from the backend. */
export interface BackendComplianceFlag {
  rule: string;
  severity: "low" | "medium" | "high" | "critical";
  banned_phrase: string;
  suggestion: string;
}

/** POST /api/v1/chat response body — the full pipeline output. */
export interface AIResponse {
  query_category: string;
  raw_data: Record<string, unknown>;
  draft_response: string;
  compliance_passed: boolean;
  compliance_flags: BackendComplianceFlag[];
  revision_count: number;
  final_response: string;
  disclaimer: string;
  latency_ms: number;
  timestamp: string;
  conversation_id?: string;
}
