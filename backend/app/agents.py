"""
SmartCycle — Multi-Agent Nodes (LangGraph)
============================================

Architectural synthesis from top-tier open-source projects:

  ┌────────────────────────────────────────────────────────────┐
  │ FinRobot philosophy                                        │
  │   "Deterministic Computation" ⇄ "LLM Narrative"           │
  │   The Quantitative Researcher runs TOOLS ONLY.             │
  │   The Empathy Copilot runs LLM generation ONLY.            │
  │   They NEVER mix in the same node.                         │
  ├────────────────────────────────────────────────────────────┤
  │ tradingagents philosophy                                   │
  │   The Compliance Gatekeeper is an ADVERSARIAL hard gate.   │
  │   If draft_response fails, the graph loops BACK to the     │
  │   Empathy Copilot with structured revision_notes.          │
  │   After MAX_RETRIES, compliance FORCE-OVERRIDES output.    │
  └────────────────────────────────────────────────────────────┘

Each agent is an async Python function with signature:
    async def agent_node(state: AgentState) -> Dict[str, Any]

The returned dict is a PARTIAL AgentState — LangGraph merges it into
the full state via the declared channels.

LLM STRATEGY (Phase 5):
  • Real LLM (OpenAI-compatible) when LLM_API_KEY is configured
  • Template-based mock LLM as graceful fallback
  • web_search() results injected into LLM context for real-time awareness
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ChatPromptTemplate will be used when langchain_core is available:
# from langchain_core.prompts import ChatPromptTemplate

from app.schema import (
    AgentState,
    AnxietyLevel,
    KnowledgeLevel,
    QueryCategory,
    RiskTolerance,
)
from app.tools import fetch_market_data, hybrid_retrieve, web_search

logger = logging.getLogger("smartcycle.agents")

# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

MAX_RETRIES = 3  # tradingagents: max compliance loop-back iterations

# ── Banned terms (tradingagents-style keyword blocklist) ──────
# These are regex patterns; case-insensitive matching is applied.
# In production, this would be a config-driven rule engine.

BANNED_PATTERNS: List[Tuple[str, str, str]] = [
    # (regex pattern,               severity,   suggestion)
    # ── English banned patterns ──
    (r"\bguaranteed?\b",            "critical", "Replace with 'historically' or 'has shown'."),
    (r"\bmust\s+buy\b",             "critical", "Remove imperative; rephrase as 'may consider'."),
    (r"\bno\s+risk\b",              "critical", "No investment is risk-free. Add risk disclosure."),
    (r"\brisk[-\s]?free\s+(?:invest|product|strategy|solution|return|profit|money|asset)\b", "critical", "Replace with 'lower-risk' or 'capital-preservation-oriented'."),
    # NOTE: "risk-free rate" is a legitimate financial term, intentionally NOT blocked.
    (r"\bdefinitely\b",             "high",     "Replace with 'may' or 'could potentially'."),
    (r"\bcertainly\b",              "high",     "Replace with 'in many cases' or 'historically'."),
    (r"\b100%\s*(safe|secure)\b",   "critical", "Remove absolute safety claim entirely."),
    (r"\bcan['']t\s+lose\b",        "critical", "Remove; all investments carry loss potential."),
    (r"\bguaranteed?\s+returns?\b", "critical", "Replace with 'target returns' or 'expected returns'."),
    # ── Chinese banned patterns (for demo + production) ──
    (r"保本",                       "critical", "Replace with '本金保护策略' or 'capital preservation oriented'."),
    (r"保证\s*收益",                "critical", "Remove; use '目标收益' or '历史收益参考' instead."),
    (r"保证\s*盈利",                "critical", "Remove; no returns can be promised."),
    (r"稳赚不赔",                   "critical", "Remove entirely; all investments carry risk."),
    (r"稳赚",                       "critical", "Replace with '追求稳健回报' with risk caveats."),
    (r"绝对\s*安全",                "critical", "Remove; no financial product is absolutely safe."),
    (r"100%\s*安全",               "critical", "Remove absolute safety claim."),
    (r"无\s*风险",                  "critical", "Replace with '低风险' or '风险可控'."),
    (r"零\s*风险",                  "critical", "Remove; zero-risk claims violate regulations."),
    (r"一定\s*赚",                  "critical", "Replace with '可能获得' or '有机会实现'."),
    (r"肯定\s*不[会能]\s*亏",       "critical", "Remove; cannot promise loss avoidance."),
    (r"包\s*赚",                    "critical", "Remove entirely."),
    (r"只赚不赔",                   "critical", "Remove; violates securities regulations."),
    (r"必然\s*上涨",                "high",     "Replace with '有上涨潜力' or '可能上涨'."),
    (r"肯定\s*涨",                  "high",     "Replace with '有上涨空间' or '趋势向好'."),
    (r"绝对\s*收益",                "high",     "Replace with '预期收益' or '参考收益'."),
    (r"承诺\s*收益",                "critical", "Remove; investment returns cannot be promised."),
]

# ── Hardcoded risk disclaimer (appended to every final_response) ──
RISK_DISCLAIMER = (
    "\n\n---\n"
    "⚠️ **风险提示 / Risk Disclosure**: "
    "本内容由AI生成，仅供参考，不构成任何投资建议。"
    "投资有风险，入市需谨慎。过往业绩不预示未来表现。"
    "请在做出投资决策前咨询持牌专业顾问。"
    "\n"
    "**Disclaimer**: This content is AI-generated and for informational purposes only. "
    "It does not constitute investment advice. All investments carry risk, including "
    "possible loss of principal. Past performance does not guarantee future results. "
    "Consult a licensed financial advisor before making investment decisions."
    f"\n\n*Compliance check timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}*"
)


# ═══════════════════════════════════════════════════════════════
# Node 1 — Router Agent
# ═══════════════════════════════════════════════════════════════
#
# DESIGN NOTE:
#   Inspired by OpenBB's command router: classify the intent before
#   dispatching to tool pipelines.  This is a DETERMINISTIC classifier
#   (keyword + pattern matching) — no LLM call needed at this stage.
#   In Phase 3, this can be upgraded to a lightweight fine-tuned model.

_ROUTER_PATTERNS: Dict[str, List[str]] = {
    QueryCategory.DATA_FETCHING.value: [
        r"(?:what|how\s+much|price|quote|P/E|PE|pb|dividend|yield|volume|market\s+cap)",
        r"(?:股价|价格|多少钱|市盈率|市净率|分红|成交量|市值)",
        r"(?:current|today|latest|now)",
    ],
    QueryCategory.EMOTIONAL_SUPPORT.value: [
        r"(?:panic|scared|worried|anxious|nervous|afraid|stress|upset|regret)",
        r"(?:恐慌|害怕|担心|焦虑|紧张|后悔|睡不着|亏|跌惨)",
        r"(?:loss|lost|losing|crash|crashing|tank)",
    ],
    QueryCategory.RESEARCH.value: [
        r"(?:analyz|research|compare|sector|industry|trend|outlook|forecast|strategy)",
        r"(?:分析|研究|比较|行业|板块|趋势|展望|预测|策略|怎么看)",
        r"(?:should\s+I|could\s+I|would\s+you|recommend|suggest|advise)",
    ],
}


async def router_node(state: AgentState) -> Dict[str, Any]:
    """Classify the user query into one of three categories.

    ROUTING TAXONOMY (OpenBB-inspired):
      • data_fetching     → "What's the price of X?" — tool-only pipeline
      • research          → "Analyze the EV sector" — RAG + LLM pipeline
      • emotional_support → "I'm panicking" — empathy-heavy pipeline

    This node performs PURE CLASSIFICATION.  It does not fetch data
    or generate text.  The classification drives downstream node behavior.

    Args:
        state: Current AgentState with at least the 'query' key populated.

    Returns:
        Partial state with 'query_category' set.
    """
    query = state.get("query", "").strip()
    query_lower = query.lower()

    # ── Score each category by regex matches ──
    scores: Dict[str, int] = {}
    for category, patterns in _ROUTER_PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, query_lower))
        scores[category] = hits

    # ── Determine winner ──
    best_category = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best_category] == 0:
        # Default fallback — treat as research
        best_category = QueryCategory.RESEARCH.value

    return {
        "query_category": best_category,
    }


# ═══════════════════════════════════════════════════════════════
# Node 2 — Quantitative Researcher (FinRobot-style)
# ═══════════════════════════════════════════════════════════════
#
# CORE PRINCIPLE (FinRobot):
#   This node runs DETERMINISTIC TOOLS ONLY.
#   It fetches structured market data (OpenBB pattern) and
#   retrieves relevant documents (FinRAG pattern).
#   It produces ZERO narrative text — only structured facts.
#
#   The LLM-powered narrative is the EXCLUSIVE responsibility
#   of the Empathy Copilot (Node 3).

def _extract_ticker(query: str) -> Optional[str]:
    """Extract stock ticker from query using simple patterns.

    In production: use a NER model or an LLM with function calling.
    """
    # Match Chinese A-share codes (6 digits)
    m = re.search(r"\b(6\d{5})\b", query)
    if m:
        return m.group(1)
    # Match common Western tickers
    for ticker in ["NVDA", "AAPL", "TSLA", "MSFT", "GOOGL"]:
        if ticker.lower() in query.lower():
            return ticker
    # Match CSI 300 mentions
    if re.search(r"(?:CSI\s*300|沪深\s*300|沪深300|000300)", query, re.IGNORECASE):
        return "000300"
    return None


async def quantitative_researcher_node(state: AgentState) -> Dict[str, Any]:
    """Fetch market data and RAG context.  NO narrative generation.

    FinRobot WORKFLOW:
      1. Extract ticker(s) from query (deterministic).
      2. Call fetch_market_data() for structured market facts (OpenBB).
      3. Call hybrid_retrieve() for semantic document context (FinRAG).
      4. Bundle everything into raw_data dict.
      5. RETURN — do NOT generate prose.

    The raw_data dict is the sole bridge between deterministic
    computation and LLM narrative.

    Args:
        state: AgentState with query and query_category.

    Returns:
        Partial state with 'raw_data' populated.
    """
    query = state.get("query", "")
    query_category = state.get("query_category", QueryCategory.RESEARCH.value)

    # ── Step 1: Extract ticker ──
    ticker = _extract_ticker(query)

    # ── Step 2: Fetch market data (OpenBB-style) ──
    market_data: Dict[str, Any] = {}
    if ticker:
        result = fetch_market_data.invoke({"symbol": ticker})
        market_data[ticker] = result
    else:
        # For research/emotional queries without a ticker, fetch CSI 300 as context
        if query_category != QueryCategory.DATA_FETCHING.value:
            benchmark = fetch_market_data.invoke({"symbol": "000300"})
            market_data["000300"] = benchmark

    # ── Step 3: Hybrid retrieval (FinRAG-style) ──
    rag_result = hybrid_retrieve.invoke({"query": query, "top_k": 3})

    # ── Step 4: Web search for real-time context ──
    web_context = web_search(query, max_results=3)

    # ── Step 5: Bundle into raw_data ──
    # IMPORTANT: raw_data is a STRUCTURED DICT, not prose.
    # The Empathy Copilot will interpret this dict later.
    raw_data: Dict[str, Any] = {
        "market_data": market_data,
        "rag_context": rag_result.get("results", []) if rag_result.get("status") == "ok" else [],
        "web_context": web_context,
        "extracted_ticker": ticker,
        "data_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"raw_data": raw_data}


# ═══════════════════════════════════════════════════════════════
# Node 3 — Empathy Copilot
# ═══════════════════════════════════════════════════════════════
#
# CORE PRINCIPLE:
#   This is the SOLE text-generation node.  It reads raw_data
#   (deterministic facts from Node 2) and client_profile (user
#   psychology from the request) and produces a calibrated narrative.
#
#   Tone calibration matrix (based on client_profile):
#     • High anxiety   → extra empathy, validation, hand-holding
#     • Beginner       → zero jargon, simple analogies
#     • Conservative   → emphasize capital preservation
#     • Aggressive     → acknowledge growth orientation, flag risks
#
#   In Phase 2, the LLM call is MOCKED with template logic.
#   In Phase 3, this becomes a ChatOpenAI invocation.

def _mock_llm_generate(
    query: str,
    query_category: str,
    raw_data: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    revision_notes: Optional[List[str]] = None,
) -> str:
    """Mock LLM narrative generation — template-based for Phase 2.

    In Phase 3, replace with:
        prompt = COPILOT_PROMPT_TEMPLATE.format(...)
        response = await llm.ainvoke(prompt)
        return response.content

    The template logic here is deliberately structured so the
    Phase 3 migration is a drop-in replacement of this function.
    """
    profile = profile or {}
    anxiety = profile.get("anxiety_level", "medium")
    knowledge = profile.get("knowledge_level", "beginner")
    risk = profile.get("risk_tolerance", "moderate")
    horizon = profile.get("investment_horizon", "medium")

    # ── Extract facts from raw_data ──
    market_data = raw_data.get("market_data", {})
    rag_docs = raw_data.get("rag_context", [])
    ticker = raw_data.get("extracted_ticker")

    # ── Build contextual intro based on query_category ──
    # Include the user's actual query for personalization
    query_ref = f'关于您的问题"{query[:60]}{"..." if len(query) > 60 else ""}"，'
    if query_category == QueryCategory.EMOTIONAL_SUPPORT.value:
        intro = query_ref + "\n\n" + _build_empathy_intro(anxiety)
    elif query_category == QueryCategory.DATA_FETCHING.value:
        intro = query_ref + _build_data_intro(ticker, market_data, knowledge)
    else:
        intro = query_ref + _build_research_intro(query, rag_docs, knowledge)

    # ── Build market facts section ──
    facts = _build_facts_section(market_data, rag_docs, knowledge)

    # ── Build risk-calibrated guidance ──
    guidance = _build_guidance(risk, horizon, anxiety)

    # ── Handle revision notes (if this is a compliance retry) ──
    revision_block = ""
    if revision_notes:
        revision_block = "\n\n[合规修订 / Compliance Revisions]\n"
        for i, note in enumerate(revision_notes, 1):
            revision_block += f"  {i}. {note}\n"

    # ── Assemble final draft ──
    draft = f"{intro}\n\n{facts}\n\n{guidance}{revision_block}"
    return draft


def _build_empathy_intro(anxiety: str) -> str:
    """Open with emotional validation for stressed investors."""
    if anxiety == AnxietyLevel.HIGH.value:
        return (
            "我完全理解您此刻的担忧。市场波动确实会让人感到不安，"
            "许多投资者在类似的行情下也会有同样的感受。"
            "请让我为您梳理一下当前的情况，帮助您更清晰地看待市场。\n\n"
            "I understand your concern completely. Market fluctuations can be deeply "
            "unsettling, and many investors share these feelings during volatile periods. "
            "Let me help you understand the current situation more clearly."
        )
    elif anxiety == AnxietyLevel.MEDIUM.value:
        return (
            "感谢您的提问。当前市场环境确实有些复杂，"
            "让我为您整理一些客观的市场信息，帮助您做出更理性的判断。"
        )
    return (
        "感谢您的咨询。以下是基于当前市场数据的客观分析，供您参考。"
    )


def _build_data_intro(ticker: Optional[str], market_data: dict, knowledge: str) -> str:
    """Build a factual intro for data-fetching queries."""
    if not ticker:
        return "我未能从您的提问中识别出具体的股票代码。以下是您可以参考的信息："
    if knowledge == KnowledgeLevel.BEGINNER.value:
        return f"关于您查询的标的，以下是关键的市场数据："
    return f"以下是 {ticker} 的结构化市场数据及简要背景："


def _build_research_intro(query: str, rag_docs: list, knowledge: str) -> str:
    """Build an analytical intro for research queries."""
    doc_count = len(rag_docs)
    if knowledge == KnowledgeLevel.BEGINNER.value:
        return (
            f"关于您的问题，我查阅了近期的市场研究报告（共找到 {doc_count} 篇相关分析），"
            f"为您用通俗的语言总结如下："
        )
    return (
        f"针对您的研究问题，我检索了 {doc_count} 篇相关市场研究报告，分析如下："
    )


def _build_facts_section(
    market_data: dict, rag_docs: list, knowledge: str
) -> str:
    """Render structured data and RAG context as prose.

    IMPORTANT: This transforms raw_data into READABLE FORM.
    In Phase 3, an LLM will do this more elegantly.
    """
    lines: List[str] = []

    # ── Market data ──
    if market_data:
        lines.append("**📊 市场数据 / Market Data**")
        for symbol, data in market_data.items():
            status = data.get("status", "ok")
            if status == "ok":
                lines.append(
                    f"- {data.get('name_cn', symbol)} ({symbol}): "
                    f"¥{data.get('price', 'N/A')}, "
                    f"涨跌幅 {data.get('change_pct', 0):+.2f}%, "
                    f"市盈率(TTM) {data.get('pe_ttm', 'N/A')}x"
                )
                if knowledge != KnowledgeLevel.BEGINNER.value:
                    lines.append(
                        f"  52周区间: ¥{data.get('52w_low', 'N/A')} – "
                        f"¥{data.get('52w_high', 'N/A')}, "
                        f"Beta: {data.get('beta', 'N/A')}"
                    )
            else:
                lines.append(f"- {symbol}: {data.get('note', '数据暂不可用')}")

    # ── RAG context ──
    if rag_docs:
        lines.append("\n**📰 相关研究 / Relevant Research**")
        for i, doc in enumerate(rag_docs, 1):
            source = doc.get("source", "Unknown")
            title = doc.get("title", "")
            snippet = doc.get("snippet", "")
            # Truncate for readability
            if knowledge == KnowledgeLevel.BEGINNER.value and len(snippet) > 200:
                snippet = snippet[:200] + "..."
            lines.append(f"\n{i}. *{title}* ({source})")
            lines.append(f"   {snippet}")

    if not lines:
        lines.append("当前暂无相关市场数据。")

    return "\n".join(lines)


def _build_guidance(risk: str, horizon: str, anxiety: str) -> str:
    """Build risk-calibrated guidance section.

    This is the structural bridge between facts and advice.
    In Phase 3, this is where the LLM adds the most value.
    """
    guidance_lines = ["**💡 分析要点 / Key Takeaways**"]

    # Risk-aware framing
    if risk == RiskTolerance.CONSERVATIVE.value:
        guidance_lines.append(
            "- 考虑到您的保守型风险偏好，建议优先关注资本保值和稳定现金流资产。"
        )
    elif risk == RiskTolerance.AGGRESSIVE.value:
        guidance_lines.append(
            "- 您的进取型风险偏好意味着您可以承受较大的短期波动以换取长期收益，"
            "但仍需注意仓位管理和分散投资。"
        )
    else:
        guidance_lines.append(
            "- 基于您的稳健型风险偏好，建议在成长性和防御性资产之间保持均衡配置。"
        )

    # Horizon framing
    if horizon == "short":
        guidance_lines.append(
            "- 短期投资视角下，市场情绪和流动性是主要驱动因素，请注意短期波动风险。"
        )
    elif horizon == "long":
        guidance_lines.append(
            "- 长期投资视角下，基本面（盈利、行业趋势、政策方向）比短期价格波动更为重要。"
        )

    # Anxiety buffer
    if anxiety == AnxietyLevel.HIGH.value:
        guidance_lines.append(
            "\n⚡ **特别提醒**: 如果您感到过度焦虑，建议暂时远离行情页面，"
            "与您的投资顾问进行一次面对面的沟通。情绪化决策是投资中最常见的亏损原因之一。"
        )

    return "\n".join(guidance_lines)


# ═══════════════════════════════════════════════════════════════
# Real LLM Prompt Builders (Phase 5)
# ═══════════════════════════════════════════════════════════════


def _build_system_prompt() -> str:
    """Build the Copilot's system prompt with role, tone, and compliance rules.

    This is the "personality" of the SmartCycle Copilot — it defines
    what the AI IS and what it MUST NEVER DO.
    """
    return (
        "你是一位专业的金融投资顾问 AI，名为 SmartCycle Copilot（智循助手）。\n"
        "你的职责是为客户提供客观、清晰、有同理心的市场分析和投资参考信息。\n\n"
        "## 核心原则\n"
        "1. **客观中立**：你提供的是信息和分析，绝不构成投资建议。\n"
        "2. **合规第一**：严格遵守金融监管要求，绝不使用绝对化、承诺性语言。\n"
        "3. **风险意识**：所有回复必须提及投资风险。\n"
        "4. **同理心**：根据客户情绪状态调整语气，对焦虑的客户给予情感支持。\n"
        "5. **通俗易懂**：根据客户知识水平调整专业术语的使用密度。\n\n"
        "## 严格禁止使用的词语\n"
        "- 绝不使用：保本、保证收益、稳赚不赔、稳赚、零风险、无风险、只赚不赔、包赚、100%安全、绝对安全、一定赚\n"
        "- 绝不使用：guaranteed, risk-free, no risk, must buy, can't lose, 100% safe, definitely, certainly\n"
        '- 替代方案：用「历史表现」代替「保证」，用「有上涨潜力」代替「必然上涨」，用「追求稳健回报」代替「稳赚」\n\n'
        "## 回复格式\n"
        "1. 以对客户问题的共情或确认开头\n"
        "2. 提供客观的市场数据和分析\n"
        "3. 给出风险校准后的参考要点\n"
        "4. 必要时附上合规修订说明\n"
        "5. 结尾始终包含风险提示\n\n"
        "请始终使用简体中文回复（可包含必要的英文术语），语气专业但温暖。"
    )


def _build_user_prompt(
    query: str,
    query_category: str,
    raw_data: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    revision_notes: Optional[List[str]],
) -> str:
    """Build the user prompt with all available context injected.

    This is the "briefing" — it gives the LLM everything it needs
    to produce a calibrated response.
    """
    profile = profile or {}
    sections: List[str] = []

    # ── Section 1: The query ──
    sections.append(f"## 用户问题\n{query}")

    # ── Section 2: Query classification ──
    category_labels = {
        "data_fetching": "行情查询",
        "research": "研究分析",
        "emotional_support": "情绪支持",
    }
    label = category_labels.get(query_category, query_category)
    sections.append(f"\n## 问题类型\n{label}")

    # ── Section 3: Client profile (tone calibration) ──
    risk = profile.get("risk_tolerance", "moderate")
    anxiety = profile.get("anxiety_level", "medium")
    knowledge = profile.get("knowledge_level", "beginner")
    horizon = profile.get("investment_horizon", "medium")

    anxiety_hint = {
        "high": "客户非常焦虑，请先充分共情和安抚，再提供信息。",
        "medium": "客户有一定担忧，请用温和的语气。",
        "low": "客户情绪稳定，可以使用更直接的分析风格。",
    }.get(anxiety, "")

    knowledge_hint = {
        "beginner": "客户是投资新手，请避免使用复杂金融术语，用通俗比喻解释。",
        "intermediate": "客户有一定基础，可以适度使用专业术语。",
        "advanced": "客户经验丰富，可以使用专业分析语言。",
    }.get(knowledge, "")

    risk_hint = {
        "conservative": "客户是保守型投资者，请强调资本保值和风险控制。",
        "moderate": "客户是稳健型投资者，请在成长性和防御性之间保持平衡。",
        "aggressive": "客户是进取型投资者，可讨论成长机会但必须提示风险。",
    }.get(risk, "")

    sections.append(
        f"\n## 客户画像\n"
        f"- 风险偏好: {risk}\n"
        f"- 焦虑程度: {anxiety}\n"
        f"- 知识水平: {knowledge}\n"
        f"- 投资期限: {horizon}\n"
        f"**语气指导**: {anxiety_hint}\n"
        f"**语言指导**: {knowledge_hint}\n"
        f"**风险指导**: {risk_hint}"
    )

    # ── Section 4: Market data (structured facts) ──
    market_data = raw_data.get("market_data", {})
    if market_data:
        sections.append(f"\n## 市场数据\n```json\n{json.dumps(market_data, ensure_ascii=False, indent=2, default=str)}\n```")

    # ── Section 5: RAG context ──
    rag_context = raw_data.get("rag_context", [])
    if rag_context:
        sections.append(f"\n## 知识库检索结果\n{json.dumps(rag_context, ensure_ascii=False, indent=2, default=str)}")

    # ── Section 6: Web search context ──
    web_context = raw_data.get("web_context", [])
    if web_context:
        web_text = "\n".join(
            f"- **{r.get('title', '')}**: {r.get('snippet', '')}"
            for r in web_context
        )
        sections.append(f"\n## 实时网络信息\n{web_text}")

    # ── Section 7: Revision notes (if this is a retry) ──
    if revision_notes:
        notes_text = "\n".join(f"- {n}" for n in revision_notes)
        sections.append(
            f"\n## ⚠️ 合规修订要求\n"
            f"上一次回复未通过合规审查。请根据以下反馈重写：\n{notes_text}\n"
            f"重要：不要重复之前的错误！请使用建议的替代措辞。"
        )

    return "\n".join(sections)


async def _real_llm_generate(
    query: str,
    query_category: str,
    raw_data: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    revision_notes: Optional[List[str]] = None,
) -> str:
    """Generate narrative using a real LLM (OpenAI-compatible).

    If LLM_API_KEY is not configured, falls back to _mock_llm_generate().

    Args:
        query:           User's original query.
        query_category:  Router classification.
        raw_data:        Structured facts from the Researcher node.
        profile:         Client psychological/financial profile.
        revision_notes:  Compliance feedback (if this is a retry).

    Returns:
        Generated narrative text (Chinese + English mixed).
    """
    from app.llm import get_llm, is_real_llm

    if not is_real_llm():
        logger.info("[agents] No LLM_API_KEY configured — using template-based mock")
        return _mock_llm_generate(query, query_category, raw_data, profile, revision_notes)

    llm = get_llm()
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(query, query_category, raw_data, profile, revision_notes)

    try:
        response = await llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        if response and len(response.strip()) > 10:
            logger.info("[agents] Real LLM: %d chars generated", len(response))
            return response
        logger.warning("[agents] LLM returned empty/short response, falling back to mock")
    except Exception as exc:
        logger.warning("[agents] LLM call failed, falling back to mock: %s", exc)

    # Graceful fallback
    return _mock_llm_generate(query, query_category, raw_data, profile, revision_notes)


async def empathy_copilot_node(state: AgentState) -> Dict[str, Any]:
    """Generate a personalized, tone-calibrated draft response.

    This node consumes:
      • raw_data        (deterministic facts from the Researcher)
      • client_profile  (psychological profile for tone modulation)
      • revision_notes  (compliance feedback, if this is a retry)

    And produces:
      • draft_response  (natural-language narrative for the end-user)

    In Phase 2, the LLM is mocked.  The template logic mirrors exactly
    what an LLM prompt chain would produce:
      1. Empathy intro (calibrated to anxiety_level)
      2. Facts section (rendered from raw_data, calibrated to knowledge_level)
      3. Guidance section (calibrated to risk_tolerance & horizon)
      4. Revision block (only if this is a compliance retry)

    Args:
        state: AgentState with raw_data, client_profile, and optionally
               revision_notes from a prior compliance failure.

    Returns:
        Partial state with 'draft_response' set.
    """
    query = state.get("query", "")
    query_category = state.get("query_category", QueryCategory.RESEARCH.value)
    raw_data = state.get("raw_data", {})
    profile = state.get("client_profile") or {}
    revision_notes = state.get("revision_notes") or []

    # ── LLM CALL (real or mock) ──
    # Phase 5: Uses real LLM when LLM_API_KEY is configured;
    # falls back to template-based _mock_llm_generate() otherwise.
    draft = await _real_llm_generate(query, query_category, raw_data, profile, revision_notes)

    # ── Clear revision notes (consumed in this iteration) ──
    return {
        "draft_response": draft,
        "revision_notes": [],
    }


# ═══════════════════════════════════════════════════════════════
# Node 4 — Compliance Gatekeeper (tradingagents-style)
# ═══════════════════════════════════════════════════════════════
#
# CORE PRINCIPLE (tradingagents):
#   This node acts as an ADVERSARIAL HARD GATE.
#   It does not trust the Empathy Copilot's output.
#   It actively searches for violations and, if found:
#     A) Sets compliance_passed = False
#     B) Populates revision_notes with structured critique
#     C) The graph routes BACK to the Empathy Copilot
#   If the draft passes: it appends the mandatory risk disclaimer
#   and releases the final_response.
#
#   After MAX_RETRIES failed attempts, the Gatekeeper FORCE-OVERRIDES
#   the output with a hardcoded risk disclosure — the system's
#   regulatory obligation overrides user experience.

# ── Suitability guardrails ──
# Maps risk_tolerance → acceptable asset-class suggestions
SUITABILITY_MAP: Dict[str, Dict[str, Any]] = {
    RiskTolerance.CONSERVATIVE.value: {
        "allowed_terms": ["债券", "货币基金", "存款", "国债", "高评级", "bond", "treasury", "money market"],
        "flagged_terms": ["杠杆", "期权", "期货", "做空", "杠杆ETF", "option", "future", "leverage", "short"],
        "max_equity_pct_note": "保守型投资者权益类资产配置一般不超过20%",
    },
    RiskTolerance.MODERATE.value: {
        "allowed_terms": ["混合", "平衡", "指数基金", "ETF", "蓝筹", "balanced", "index", "blue chip"],
        "flagged_terms": ["全仓", "重仓单票", "集中持股", "all-in", "YOLO"],
        "max_equity_pct_note": "稳健型投资者权益类资产配置一般不超过50%",
    },
    RiskTolerance.AGGRESSIVE.value: {
        "allowed_terms": [],
        "flagged_terms": ["借钱投资", "贷款炒股", "borrow to invest", "leveraged loan"],
        "max_equity_pct_note": "进取型投资者也应注意分散投资，避免单一标的过度集中",
    },
}


async def compliance_gatekeeper_node(state: AgentState) -> Dict[str, Any]:
    """Adversarial compliance screening of the draft response.

    tradingagents WORKFLOW (three-pass check):
      PASS 1 — Banned-Term Scan
        Regex match against BANNED_PATTERNS (absolute terms, guarantees).
        Each match → ComplianceFlag in the report.

      PASS 2 — Suitability Check
        Verify that the draft's suggestions align with the client's
        declared risk_tolerance.  Conservative investors should not
        receive aggressive product suggestions.

      PASS 3 — Disclaimer Attachment
        If both passes are clean, append the mandatory risk disclaimer
        and release as final_response.

    If PASS 1 or PASS 2 fail:
      • compliance_passed = False
      • revision_notes populated with actionable feedback
      • Graph routes BACK to Empathy Copilot for rewrite
      • iteration_count incremented (hard stop at MAX_RETRIES)

    Args:
        state: AgentState with draft_response, client_profile, and iteration_count.

    Returns:
        Partial state with compliance_passed, compliance_report,
        revision_notes, final_response, disclaimer, and iteration_count.
    """
    draft = state.get("draft_response", "")
    query = state.get("query", "")
    profile = state.get("client_profile") or {}
    iteration = state.get("iteration_count", 0)
    risk = profile.get("risk_tolerance", RiskTolerance.MODERATE.value)

    flags: List[Dict[str, str]] = []

    # ══════════════════════════════════════════════════════════
    # PASS 0 — User Query Compliance Scan
    # ══════════════════════════════════════════════════════════
    # Scan the USER'S ORIGINAL QUERY for banned terms independently
    # of the AI draft. This catches scenarios where an advisor types
    # regulated language into the chat — even if the AI output is clean,
    # the system must flag that the user used banned terminology.
    for pattern, severity, suggestion in BANNED_PATTERNS:
        for match in re.finditer(pattern, query, re.IGNORECASE):
            flags.append({
                "rule": f"USER_QUERY_BANNED_TERM:{pattern}",
                "severity": severity,
                "banned_phrase": match.group(0),
                "suggestion": f"您在提问中使用了不合规术语'{match.group(0)}'。{suggestion}",
            })

    # ══════════════════════════════════════════════════════════
    # PASS 1 — Banned-Term Scan (regex) on AI draft
    # ══════════════════════════════════════════════════════════
    for pattern, severity, suggestion in BANNED_PATTERNS:
        for match in re.finditer(pattern, draft, re.IGNORECASE):
            flags.append({
                "rule": f"BANNED_TERM:{pattern}",
                "severity": severity,
                "banned_phrase": match.group(0),
                "suggestion": suggestion,
            })

    # ══════════════════════════════════════════════════════════
    # PASS 2 — Suitability Check
    # ══════════════════════════════════════════════════════════
    suitability = SUITABILITY_MAP.get(risk, SUITABILITY_MAP[RiskTolerance.MODERATE.value])
    for flagged in suitability["flagged_terms"]:
        if re.search(flagged, draft, re.IGNORECASE):
            flags.append({
                "rule": "SUITABILITY:RiskMismatch",
                "severity": "high",
                "banned_phrase": flagged,
                "suggestion": (
                    f"检测到与客户风险偏好({risk})不匹配的术语'{flagged}'。"
                    f"{suitability['max_equity_pct_note']}。"
                ),
            })

    # ══════════════════════════════════════════════════════════
    # VERDICT
    # ══════════════════════════════════════════════════════════
    compliance_passed = len(flags) == 0
    revision_notes: List[str] = []

    if compliance_passed:
        # ── PASS 3: Attach disclaimer & release ──
        final = draft + RISK_DISCLAIMER
        return {
            "compliance_passed": True,
            "compliance_report": {"flags": [], "risk_rating": _assess_risk_rating(draft, profile), "passed": True},
            "final_response": final,
            "disclaimer": RISK_DISCLAIMER,
            "iteration_count": iteration + 1,
        }

    # ── FAILED — determine remedy ──
    # MAX_RETRIES - 1 because the loop guard exits when iter == MAX_RETRIES.
    # This ensures the force-override fires on the LAST retry attempt.
    if iteration >= MAX_RETRIES - 1:
        # FORCE OVERRIDE (tradingagents hard-gate fallback)
        # After max retries, the system's regulatory obligation supersedes UX.
        query = state.get("query", "")
        quoted = query[:80] + ("..." if len(query) > 80 else "")
        force_response = (
            f"我们无法针对您的请求「{quoted}」生成合规的个性化回复。"
            "以下是标准化的市场信息及风险提示。\n\n"
            "We were unable to generate a compliant personalized response for your query. "
            "Below is standardized market information and risk disclosures.\n\n"
            "请咨询您的持牌投资顾问以获取个性化建议。\n"
            "Please consult your licensed financial advisor for personalized advice."
        )
        return {
            "compliance_passed": False,
            "compliance_report": {
                "flags": flags,
                "risk_rating": "blocked",
                "passed": False,
                "force_override": True,
            },
            "final_response": force_response + RISK_DISCLAIMER,
            "disclaimer": RISK_DISCLAIMER,
            "revision_notes": [],
            "iteration_count": iteration + 1,
        }

    # ── Retry: build revision notes for the Copilot ──
    # IMPORTANT: Do NOT include the literal banned_phrase in the note —
    # otherwise it will be re-detected on the next compliance pass,
    # creating an infinite retry loop.
    for f in flags:
        # Mask the banned phrase so it doesn't re-trigger
        masked_phrase = f['banned_phrase'][:2] + "***" + f['banned_phrase'][-1:] if len(f['banned_phrase']) > 3 else "***"
        revision_notes.append(
            f"[{f['severity'].upper()}] {f['rule']}: "
            f"违规术语({masked_phrase}) — {f['suggestion']}"
        )

    return {
        "compliance_passed": False,
        "compliance_report": {
            "flags": flags,
            "risk_rating": _assess_risk_rating(draft, profile),
            "passed": False,
        },
        "revision_notes": revision_notes,
        "iteration_count": iteration + 1,
    }


def _assess_risk_rating(draft: str, profile: dict) -> str:
    """Heuristic risk rating of the draft relative to client profile.

    In production: this would be an LLM-as-judge evaluation.
    """
    risk = profile.get("risk_tolerance", "moderate")
    draft_lower = draft.lower()

    aggressive_signals = ["leverage", "option", "future", "杠杆", "期权", "期货", "做空"]
    conservative_signals = ["bond", "treasury", "deposit", "债券", "国债", "存款", "货币基金"]

    agg_count = sum(1 for s in aggressive_signals if s in draft_lower)
    con_count = sum(1 for s in conservative_signals if s in draft_lower)

    if risk == RiskTolerance.CONSERVATIVE.value and agg_count > 0:
        return "mismatch_conservative"
    if risk == RiskTolerance.AGGRESSIVE.value and con_count > 3:
        return "mismatch_aggressive"
    if agg_count > 2:
        return "aggressive"
    return "appropriate"
