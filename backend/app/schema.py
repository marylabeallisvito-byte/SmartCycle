"""
SmartCycle — Pydantic Schemas & LangGraph AgentState
=====================================================

Architectural synthesis from top-tier open-source projects:
  • OpenBB / FinRAG  → separation of "raw market data" vs "semantic document retrieval"
  • FinRobot         → strict split between deterministic computation and LLM narrative
  • tradingagents    → adversarial compliance gate with conditional loop-back

All API I/O is validated at the boundary with Pydantic V2.
The LangGraph runtime uses a TypedDict (required for state channel inference).

Compatible with Python 3.9+ — uses Optional / Dict / List (not PEP 604 union syntax).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Enums — shared across schema, agents, and tools
# ============================================================

class QueryCategory(str, Enum):
    """Router classification — mirrors OpenBB's command taxonomy (data vs analysis)."""
    DATA_FETCHING = "data_fetching"        # "What's the P/E of 600519?"
    RESEARCH = "research"                   # "Analyze the EV battery supply chain"
    EMOTIONAL_SUPPORT = "emotional_support" # "I can't sleep because of my losses"


class RiskTolerance(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AnxietyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InvestmentHorizon(str, Enum):
    SHORT = "short"       # < 1 year
    MEDIUM = "medium"     # 1–5 years
    LONG = "long"         # > 5 years


class KnowledgeLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


# ============================================================
# LangGraph AgentState (TypedDict — required by LangGraph)
# ============================================================
#
# DESIGN NOTE (FinRobot philosophy):
#   The state separates "raw_data" (deterministic, tool-fetched) from
#   "draft_response" (LLM-generated narrative).  No LLM text is produced
#   until the Quantitative Researcher has fully populated raw_data.
#
# DESIGN NOTE (tradingagents philosophy):
#   "compliance_passed" is a Boolean gate.  If False, the graph routes
#   BACK to the Empathy Copilot with revision_notes.  After max 3 retries,
#   the Compliance Gatekeeper force-overrides with a hardcoded disclaimer.

class AgentState(TypedDict):
    """State dictionary that flows through every LangGraph node.

    LangGraph requires TypedDict (not Pydantic) for state-channel inference.
    Each key is a channel; nodes may read/write any subset.
    """

    # --- Input ---
    query: str
    client_profile: Optional[dict]        # serialized ClientProfile

    # --- Router ---
    query_category: str                   # one of QueryCategory values

    # --- Quantitative Researcher (FinRobot: deterministic facts ONLY) ---
    raw_data: dict                        # {market_data: {...}, rag_context: [...]}

    # --- Empathy Copilot ---
    draft_response: str                   # LLM-generated narrative (pre-compliance)

    # --- Compliance Gatekeeper (tradingagents: adversarial check) ---
    compliance_passed: bool               # True → proceed to END
    compliance_report: dict               # {flags: [...], risk_rating: str}
    revision_notes: List[str]             # feedback for the Copilot if retry needed
    final_response: str                   # the compliance-cleaned text the user sees
    disclaimer: str                       # mandatory risk disclaimer

    # --- Loop guard (prevents infinite retries) ---
    iteration_count: int                  # incremented on each Compliance → Copilot loop

    # --- Metadata ---
    latency_ms: float
    timestamp: str


# ============================================================
# API Request Models
# ============================================================

class ClientProfile(BaseModel):
    """Psychological + financial profile of the end-investor.

    Drives tone calibration in the Empathy Copilot and suitability
    checks in the Compliance Gatekeeper (tradingagents-style).
    """
    risk_tolerance: RiskTolerance = Field(
        default=RiskTolerance.MODERATE,
        description="Investor's stated risk appetite.",
    )
    anxiety_level: AnxietyLevel = Field(
        default=AnxietyLevel.MEDIUM,
        description="Current emotional state. Drives empathy modulation.",
    )
    investment_horizon: InvestmentHorizon = Field(
        default=InvestmentHorizon.MEDIUM,
        description="Expected investment time frame.",
    )
    knowledge_level: KnowledgeLevel = Field(
        default=KnowledgeLevel.BEGINNER,
        description="Financial literacy — controls jargon density.",
    )
    age_range: Optional[str] = Field(
        default=None,
        pattern=r"^\d{2}-\d{2}$",
        description="Age bracket, e.g. '25-35'.",
    )
    portfolio_value_yuan: Optional[float] = Field(
        default=None,
        ge=0,
        description="Approximate portfolio size in CNY.",
    )

    @field_validator("age_range")
    @classmethod
    def validate_age_bracket(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            lo, hi = v.split("-")
            if int(lo) >= int(hi):
                raise ValueError("age_range must be increasing, e.g. '25-35'")
        return v

    def to_dict(self) -> dict:
        """Serialize for the TypedDict state channel."""
        return self.model_dump()


class AdvisorQuery(BaseModel):
    """Inbound request to POST /api/v1/chat."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=4_000,
        description="Natural-language question from advisor or investor.",
        examples=[
            "Should I rotate out of tech ETFs this quarter?",
            "最近市场波动这么大，我该不该清仓？",
        ],
    )
    client_profile: Optional[ClientProfile] = Field(
        default=None,
        description="Optional. If absent, the system uses sensible defaults.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="For multi-turn correlation.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Passthrough flags (A/B tests, feature gates, etc.).",
    )

    @field_validator("query")
    @classmethod
    def strip_and_warn(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Query must be at least 2 characters after stripping.")
        return cleaned


# ============================================================
# API Response Models
# ============================================================

class ComplianceFlag(BaseModel):
    """One violation detected by the Compliance Gatekeeper."""
    rule: str
    severity: Literal["low", "medium", "high", "critical"]
    banned_phrase: str
    suggestion: str


class AIResponse(BaseModel):
    """Complete response returned to the frontend after the full pipeline.

    Every field is populated — the frontend chooses what to display.
    """
    # Routing
    query_category: str

    # Deterministic data (OpenBB / FinRAG layer)
    raw_data: dict = Field(default_factory=dict)

    # Narrative (pre-compliance)
    draft_response: str

    # Compliance verdict (tradingagents gate)
    compliance_passed: bool
    compliance_flags: List[ComplianceFlag] = Field(default_factory=list)
    revision_count: int = Field(default=0)

    # Final (post-compliance, user-facing)
    final_response: str
    disclaimer: str

    # Metadata
    latency_ms: float = 0.0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    conversation_id: Optional[str] = None
