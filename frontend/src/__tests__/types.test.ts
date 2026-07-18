/**
 * SmartCycle — TypeScript Type Validation Tests
 *
 * Verifies that frontend types are consistent with the backend API contract.
 * Tests are runtime checks of shape compatibility.
 */

import { describe, expect, it } from "vitest";

// Import types (compile-time verification)
import type {
  AdvisorQuery,
  BackendClientProfile,
  BackendComplianceFlag,
  AIResponse,
} from "@/types";

// ── BackendClientProfile shape ──

describe("BackendClientProfile", () => {
  it("creates a valid conservative profile", () => {
    const profile: BackendClientProfile = {
      risk_tolerance: "conservative",
      anxiety_level: "high",
      investment_horizon: "short",
      knowledge_level: "beginner",
      age_range: "55-64",
      portfolio_value_yuan: 12_000_000,
    };

    expect(profile.risk_tolerance).toBe("conservative");
    expect(profile.anxiety_level).toBe("high");
    expect(profile.investment_horizon).toBe("short");
    expect(profile.knowledge_level).toBe("beginner");
    expect(profile.age_range).toMatch(/^\d{2}-\d{2}$/);
    expect(profile.portfolio_value_yuan).toBeGreaterThan(0);
  });

  it("creates a valid aggressive profile", () => {
    const profile: BackendClientProfile = {
      risk_tolerance: "aggressive",
      anxiety_level: "low",
      investment_horizon: "long",
      knowledge_level: "advanced",
    };

    expect(profile.risk_tolerance).toBe("aggressive");
    expect(profile.investment_horizon).toBe("long");
  });

  it("creates a valid moderate profile with optional fields omitted", () => {
    const profile: BackendClientProfile = {
      risk_tolerance: "moderate",
      anxiety_level: "medium",
      investment_horizon: "medium",
      knowledge_level: "intermediate",
    };

    expect(profile.risk_tolerance).toBe("moderate");
    expect(profile.age_range).toBeUndefined();
  });
});

// ── AdvisorQuery shape ──

describe("AdvisorQuery", () => {
  it("creates a minimal query", () => {
    const query: AdvisorQuery = {
      query: "沪深300估值如何？",
    };

    expect(query.query).toBe("沪深300估值如何？");
    expect(query.client_profile).toBeUndefined();
    expect(query.conversation_id).toBeUndefined();
  });

  it("creates a full query with client profile", () => {
    const query: AdvisorQuery = {
      query: "Should I rotate out of tech ETFs?",
      client_profile: {
        risk_tolerance: "moderate",
        anxiety_level: "medium",
        investment_horizon: "medium",
        knowledge_level: "intermediate",
      },
      conversation_id: "conv-abc-123",
      metadata: { feature_flag: "new_llm" },
    };

    expect(query.client_profile?.risk_tolerance).toBe("moderate");
    expect(query.conversation_id).toBe("conv-abc-123");
    expect(query.metadata?.feature_flag).toBe("new_llm");
  });

  it("accepts Chinese query", () => {
    const query: AdvisorQuery = {
      query: "最近市场波动这么大，我该不该清仓？",
    };

    expect(query.query.length).toBeGreaterThan(0);
    // Chinese text should be preserved
    expect(query.query).toContain("清仓");
  });
});

// ── AIResponse shape ──

describe("AIResponse", () => {
  it("creates a valid clean response (all passes)", () => {
    const response: AIResponse = {
      query_category: "research",
      raw_data: {
        market_data: {
          "000300": { price: 3987.45, change_pct: 0.58 },
        },
        rag_context: [],
      },
      draft_response: "关于沪深300指数...",
      compliance_passed: true,
      compliance_flags: [],
      revision_count: 0,
      final_response: "关于沪深300指数...\n\n---\n⚠️ 风险提示...",
      disclaimer: "\n\n---\n⚠️ 风险提示...",
      latency_ms: 1200.5,
      timestamp: "2026-07-18T12:00:00Z",
    };

    expect(response.query_category).toBe("research");
    expect(response.compliance_passed).toBe(true);
    expect(response.compliance_flags).toHaveLength(0);
    expect(response.revision_count).toBe(0);
    expect(response.final_response).toContain("风险提示");
  });

  it("creates a valid flagged response (compliance failure)", () => {
    const flag: BackendComplianceFlag = {
      rule: "BANNED_TERM:稳赚不赔",
      severity: "critical",
      banned_phrase: "稳赚不赔",
      suggestion: "Remove entirely; all investments carry risk.",
    };

    const response: AIResponse = {
      query_category: "emotional_support",
      raw_data: {},
      draft_response: "这个产品稳赚不赔...",
      compliance_passed: false,
      compliance_flags: [flag],
      revision_count: 2,
      final_response: "我们无法针对您的请求生成合规的个性化回复...",
      disclaimer: "\n\n---\n⚠️ 风险提示...",
      latency_ms: 2500.0,
      timestamp: "2026-07-18T12:01:00Z",
    };

    expect(response.compliance_passed).toBe(false);
    expect(response.compliance_flags).toHaveLength(1);
    expect(response.compliance_flags[0].severity).toBe("critical");
    expect(response.revision_count).toBe(2);
  });
});

// ── BackendComplianceFlag shape ──

describe("BackendComplianceFlag", () => {
  it("all valid severity levels are accepted", () => {
    const severities: Array<BackendComplianceFlag["severity"]> = [
      "low",
      "medium",
      "high",
      "critical",
    ];

    severities.forEach((severity) => {
      const flag: BackendComplianceFlag = {
        rule: "TEST_RULE",
        severity,
        banned_phrase: "test",
        suggestion: "Use alternative wording.",
      };
      expect(flag.severity).toBe(severity);
    });
  });
});
