/* ============================================================
   SmartCycle — Mock Data for Advisor Copilot Dashboard
   ============================================================ */

// ── Re-export canonical ChatMessage & AgentTrace from types ──
import type { ChatMessage, AgentTrace } from "@/types";
export type { ChatMessage, AgentTrace };

// ── Client types ──

export interface ClientProfile {
  id: string;
  name: string;
  nameCn: string;
  age: number;
  riskTolerance: "conservative" | "moderate" | "aggressive";
  anxietyLevel: "low" | "medium" | "high";
  investmentHorizon: "short" | "medium" | "long";
  knowledgeLevel: "beginner" | "intermediate" | "advanced";
  portfolioValueYuan: number;
  aumYuan: number;
  ytdReturnPct: number;
  avatarGradient: string;
}

export interface PortfolioAllocation {
  category: string;
  categoryCn: string;
  percentage: number;
  valueYuan: number;
  color: string;
  children?: PortfolioAllocation[];
}

// ── Clients ──

export const MOCK_CLIENTS: ClientProfile[] = [
  {
    id: "c-001",
    name: "Zhang Wei",
    nameCn: "张伟",
    age: 42,
    riskTolerance: "aggressive",
    anxietyLevel: "low",
    investmentHorizon: "long",
    knowledgeLevel: "advanced",
    portfolioValueYuan: 8_500_000,
    aumYuan: 12_000_000,
    ytdReturnPct: 18.4,
    avatarGradient: "from-[#f59e0b] to-[#ef4444]",
  },
  {
    id: "c-002",
    name: "Li Na",
    nameCn: "李娜",
    age: 35,
    riskTolerance: "moderate",
    anxietyLevel: "medium",
    investmentHorizon: "medium",
    knowledgeLevel: "intermediate",
    portfolioValueYuan: 3_200_000,
    aumYuan: 5_000_000,
    ytdReturnPct: 7.2,
    avatarGradient: "from-[#3b82f6] to-[#8b5cf6]",
  },
  {
    id: "c-003",
    name: "Wang Fang",
    nameCn: "王芳",
    age: 58,
    riskTolerance: "conservative",
    anxietyLevel: "high",
    investmentHorizon: "short",
    knowledgeLevel: "beginner",
    portfolioValueYuan: 12_000_000,
    aumYuan: 15_000_000,
    ytdReturnPct: 2.1,
    avatarGradient: "from-[#10b981] to-[#3b82f6]",
  },
  {
    id: "c-004",
    name: "Chen Ming",
    nameCn: "陈明",
    age: 29,
    riskTolerance: "aggressive",
    anxietyLevel: "low",
    investmentHorizon: "long",
    knowledgeLevel: "intermediate",
    portfolioValueYuan: 1_500_000,
    aumYuan: 2_000_000,
    ytdReturnPct: 24.7,
    avatarGradient: "from-[#ec4899] to-[#f59e0b]",
  },
];

// ── Portfolio Allocations ──

export const MOCK_ALLOCATIONS: Record<string, PortfolioAllocation[]> = {
  "c-001": [
    {
      category: "Equities",
      categoryCn: "股票",
      percentage: 55,
      valueYuan: 4_675_000,
      color: "#3b82f6",
      children: [
        { category: "A-share Tech", categoryCn: "A股科技", percentage: 25, valueYuan: 2_125_000, color: "#60a5fa" },
        { category: "A-share Consumer", categoryCn: "A股消费", percentage: 15, valueYuan: 1_275_000, color: "#3b82f6" },
        { category: "US Tech", categoryCn: "美股科技", percentage: 10, valueYuan: 850_000, color: "#818cf8" },
        { category: "HK Stocks", categoryCn: "港股", percentage: 5, valueYuan: 425_000, color: "#6366f1" },
      ],
    },
    { category: "ETFs", categoryCn: "指数基金", percentage: 20, valueYuan: 1_700_000, color: "#8b5cf6" },
    { category: "Bonds", categoryCn: "债券", percentage: 10, valueYuan: 850_000, color: "#10b981" },
    { category: "Commodities", categoryCn: "大宗商品", percentage: 8, valueYuan: 680_000, color: "#f59e0b" },
    { category: "Cash", categoryCn: "现金", percentage: 7, valueYuan: 595_000, color: "#64748b" },
  ],
  "c-002": [
    { category: "Equities", categoryCn: "股票", percentage: 35, valueYuan: 1_120_000, color: "#3b82f6" },
    { category: "ETFs", categoryCn: "指数基金", percentage: 25, valueYuan: 800_000, color: "#8b5cf6" },
    { category: "Bonds", categoryCn: "债券", percentage: 20, valueYuan: 640_000, color: "#10b981" },
    { category: "Structured", categoryCn: "结构性产品", percentage: 12, valueYuan: 384_000, color: "#ec4899" },
    { category: "Cash", categoryCn: "现金", percentage: 8, valueYuan: 256_000, color: "#64748b" },
  ],
  "c-003": [
    { category: "Bonds", categoryCn: "债券", percentage: 45, valueYuan: 5_400_000, color: "#10b981" },
    { category: "Fixed Deposits", categoryCn: "定期存款", percentage: 20, valueYuan: 2_400_000, color: "#64748b" },
    { category: "Money Market", categoryCn: "货币基金", percentage: 15, valueYuan: 1_800_000, color: "#94a3b8" },
    { category: "Blue-chip Equity", categoryCn: "蓝筹股", percentage: 15, valueYuan: 1_800_000, color: "#3b82f6" },
    { category: "Cash", categoryCn: "活期", percentage: 5, valueYuan: 600_000, color: "#475569" },
  ],
  "c-004": [
    { category: "Crypto", categoryCn: "加密货币", percentage: 35, valueYuan: 525_000, color: "#f59e0b" },
    { category: "Growth Stocks", categoryCn: "成长股", percentage: 30, valueYuan: 450_000, color: "#ef4444" },
    { category: "Options", categoryCn: "期权", percentage: 15, valueYuan: 225_000, color: "#ec4899" },
    { category: "ETFs", categoryCn: "指数基金", percentage: 10, valueYuan: 150_000, color: "#8b5cf6" },
    { category: "Cash", categoryCn: "现金", percentage: 10, valueYuan: 150_000, color: "#64748b" },
  ],
};

// ── Sample agent trace (for demo / testing the ChatInterface accordion) ──
// Available for import but not used by the main dashboard (replaced by live API data).

export const MOCK_AGENT_TRACE: AgentTrace = {
  queryCategory: "emotional_support",
  rawData: {
    marketData: {
      "000300": {
        symbol: "000300.SS",
        nameCn: "沪深300",
        price: 3987.45,
        changePct: 0.58,
        peTtm: 13.2,
      },
    },
    ragContext: [
      {
        title: "Guide: Understanding Market Volatility",
        source: "Shanghai Stock Exchange Investor Education",
        snippet:
          "Market corrections of 10-20% occur on average every 2-3 years. Historical data shows investors who maintained positions recovered within 12-18 months.",
      },
      {
        title: "Q2 2026 Fund Flow Analysis",
        source: "China Merchants Securities",
        snippet:
          "Retail investor sentiment index registered 42/100 (cautious zone). ETF inflows hit a record ¥156 billion.",
      },
    ],
  },
  draftResponse:
    "我完全理解您此刻的担忧。市场波动确实会让人感到不安...\n\n" +
    "当前沪深300指数在3987点附近，市盈率13.2倍，处于近5年中位数附近。" +
    "历史数据显示，A股市场每2-3年会出现一次10-20%的回调，" +
    "但持有12-18个月后基本都能收复失地。",
  complianceFlags: [],
  revisionCount: 0,
};

// ── Welcome messages ──

export const WELCOME_MESSAGE: ChatMessage = {
  id: "msg-welcome",
  role: "assistant",
  content:
    "您好！我是 **SmartCycle Advisor Copilot**。\n\n" +
    "我可以帮您：\n" +
    "• 📊 分析客户持仓和市场动态\n" +
    "• 💡 生成个性化的投资沟通脚本\n" +
    "• 🛡️ 确保所有输出符合合规要求\n\n" +
    "请选择左侧客户，或直接输入您的问题。",
  timestamp: new Date().toISOString(),
  compliancePassed: true,
};
