"""
SmartCycle — Portfolio Analysis Service
=========================================

Portfolio risk/return analytics, asset allocation optimization,
and benchmark comparison.

Python 3.9 compatible — no PEP 604 union syntax.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("smartcycle.services.portfolio")


class PortfolioService:
    """Portfolio analysis and optimization service.

    Usage:
        svc = PortfolioService()
        analysis = svc.analyze(holdings, total_value=1_200_000)
    """

    # Risk-free rate proxy (China 1-year government bond yield)
    RISK_FREE_RATE = 0.017  # 1.7%

    def analyze(
        self,
        holdings: List[Dict[str, Any]],
        total_value: float = 0.0,
        benchmark_returns: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Analyze a portfolio's risk and return characteristics.

        Args:
            holdings: List of holding dicts with keys: symbol, asset_class,
                      market_value_yuan, allocation_pct, beta (optional),
                      unrealized_pnl_pct (optional).
            total_value: Total portfolio value in yuan.
            benchmark_returns: Optional list of benchmark period returns for
                               Sharpe ratio calculation.

        Returns:
            Dict with keys: total_value, holdings_count, asset_allocation,
            concentration_risk, diversification_score, estimated_sharpe,
            risk_assessment, recommendations.
        """
        if not holdings:
            return {
                "total_value": total_value,
                "holdings_count": 0,
                "asset_allocation": [],
                "concentration_risk": "N/A",
                "diversification_score": 0.0,
                "risk_assessment": "No holdings data available.",
            }

        # ── Asset allocation breakdown ──
        allocation = self._compute_allocation(holdings, total_value)

        # ── Concentration risk ──
        concentration = self._compute_concentration(holdings, total_value)

        # ── Diversification score ──
        div_score = self._compute_diversification(holdings)

        # ── Estimated Sharpe ratio ──
        sharpe = self._estimate_sharpe(holdings, benchmark_returns)

        # ── Risk assessment ──
        risk_assessment = self._assess_risk(allocation, concentration, div_score)

        # ── Recommendations ──
        recommendations = self._generate_recommendations(
            allocation, concentration, div_score, risk_assessment
        )

        return {
            "total_value": round(total_value, 2),
            "total_value_formatted": self._fmt_cny(total_value),
            "holdings_count": len(holdings),
            "asset_allocation": allocation,
            "concentration_risk": concentration,
            "diversification_score": round(div_score, 2),
            "estimated_sharpe": round(sharpe, 3) if sharpe is not None else None,
            "risk_assessment": risk_assessment,
            "recommendations": recommendations,
        }

    # ── Internal Methods ────────────────────────────────────

    def _compute_allocation(
        self, holdings: List[Dict[str, Any]], total_value: float
    ) -> List[Dict[str, Any]]:
        """Group holdings by asset class and compute allocation percentages."""
        if total_value <= 0:
            total_value = sum(h.get("market_value_yuan", 0) for h in holdings)

        groups: Dict[str, Dict[str, Any]] = {}
        for h in holdings:
            asset_class = h.get("asset_class", "other")
            value = h.get("market_value_yuan", 0)
            if asset_class not in groups:
                groups[asset_class] = {
                    "asset_class": asset_class,
                    "value_yuan": 0.0,
                    "percentage": 0.0,
                    "count": 0,
                }
            groups[asset_class]["value_yuan"] += value
            groups[asset_class]["count"] += 1

        for g in groups.values():
            g["value_yuan"] = round(g["value_yuan"], 2)
            g["percentage"] = round(g["value_yuan"] / total_value * 100, 1) if total_value > 0 else 0.0

        # Sort by percentage descending
        result = sorted(groups.values(), key=lambda x: x["percentage"], reverse=True)
        return result

    def _compute_concentration(
        self, holdings: List[Dict[str, Any]], total_value: float
    ) -> Dict[str, Any]:
        """Compute concentration risk metrics."""
        if total_value <= 0:
            total_value = sum(h.get("market_value_yuan", 0) for h in holdings)

        # Top holding concentration
        sorted_holdings = sorted(holdings, key=lambda h: h.get("market_value_yuan", 0), reverse=True)
        top_1_pct = sorted_holdings[0].get("market_value_yuan", 0) / total_value * 100 if total_value > 0 else 0
        top_3_pct = sum(h.get("market_value_yuan", 0) for h in sorted_holdings[:3]) / total_value * 100 if total_value > 0 else 0

        # Herfindahl-Hirschman Index (HHI) for concentration
        hhi = sum((h.get("market_value_yuan", 0) / total_value * 100) ** 2 for h in holdings) if total_value > 0 else 0

        level = "low"
        if hhi > 2500:
            level = "high"
        elif hhi > 1500:
            level = "moderate"

        return {
            "top_holding_pct": round(top_1_pct, 1),
            "top_3_holdings_pct": round(top_3_pct, 1),
            "hhi": round(hhi, 1),
            "level": level,
        }

    def _compute_diversification(self, holdings: List[Dict[str, Any]]) -> float:
        """Compute a diversification score (0-10 scale)."""
        score = 0.0

        # Points for number of holdings (max 4)
        n = len(holdings)
        score += min(n / 5.0, 1.0) * 4.0

        # Points for asset class diversity (max 3)
        asset_classes = set(h.get("asset_class", "other") for h in holdings)
        score += min(len(asset_classes) / 4.0, 1.0) * 3.0

        # Points for balanced allocation (max 3)
        if n > 0 and sum(h.get("market_value_yuan", 0) for h in holdings) > 0:
            total = sum(h.get("market_value_yuan", 0) for h in holdings)
            max_pct = max(h.get("market_value_yuan", 0) / total for h in holdings)
            # Penalize over-concentration
            if max_pct < 0.3:
                score += 3.0
            elif max_pct < 0.5:
                score += 2.0
            elif max_pct < 0.7:
                score += 1.0

        return score

    def _estimate_sharpe(
        self,
        holdings: List[Dict[str, Any]],
        benchmark_returns: Optional[List[float]] = None,
    ) -> Optional[float]:
        """Estimate Sharpe ratio from holding returns.

        Uses unrealized PnL percentages as a rough proxy for returns.
        In production, this would use historical return series.

        NOTE: The unrealized PnL percentages are treated as period returns.
        The risk-free rate is annualized (1.7%), so we adjust it proportionally
        assuming a ~1-year holding period approximation. This is an ESTIMATE;
        for production use, replace with proper historical return series.
        """
        returns = []
        for h in holdings:
            pnl_pct = h.get("unrealized_pnl_pct")
            if pnl_pct is not None:
                returns.append(pnl_pct / 100.0)  # convert percentage to decimal

        if len(returns) < 2:
            return None

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1) if len(returns) > 1 else 0
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return None

        # NOTE: Both mean_ret (from unrealized PnL) and RISK_FREE_RATE (1.7%)
        # are treated as annual rates. If unrealized PnL represents a different
        # holding period, the risk-free rate should be adjusted accordingly.
        # This is a ROUGH ESTIMATE — for production, use historical return series.
        excess_return = mean_ret - self.RISK_FREE_RATE
        return excess_return / std_dev

    def _assess_risk(
        self,
        allocation: List[Dict[str, Any]],
        concentration: Dict[str, Any],
        diversification_score: float,
    ) -> str:
        """Generate a human-readable risk assessment."""
        equity_pct = sum(a["percentage"] for a in allocation if a["asset_class"] == "equity")

        risks = []
        if concentration["level"] == "high":
            risks.append("持仓集中度较高，建议分散投资以降低个股风险。")
        if equity_pct > 70:
            risks.append(f"权益类资产占比 {equity_pct:.0f}%，波动风险较高。")
        if diversification_score < 5:
            risks.append("资产类别过于单一，建议跨资产类别配置。")

        if not risks:
            return "投资组合风险水平适中，资产配置较为合理。"
        return " ".join(risks)

    def _generate_recommendations(
        self,
        allocation: List[Dict[str, Any]],
        concentration: Dict[str, Any],
        diversification_score: float,
        risk_assessment: str,
    ) -> List[str]:
        """Generate portfolio improvement recommendations."""
        recs = []

        if concentration["level"] in ("high", "moderate"):
            recs.append("考虑将单一持仓比例降至30%以下，以降低集中度风险。")

        asset_classes = [a["asset_class"] for a in allocation]
        if "bond" not in asset_classes and "cash" not in asset_classes:
            recs.append("建议配置一定比例的固收类资产（债券/货基）以平滑组合波动。")

        if diversification_score < 6:
            recs.append("建议增加跨行业、跨市场的资产配置以提升分散度。")

        if len(allocation) <= 2:
            recs.append("考虑增加另类资产（黄金、REITs）以增强组合韧性。")

        if not recs:
            recs.append("当前组合配置较为均衡，建议定期再平衡并关注市场变化。")

        return recs

    @staticmethod
    def _fmt_cny(value: float) -> str:
        """Format a CNY amount for display."""
        if value >= 1e8:
            return f"¥{value / 1e8:.1f}亿"
        if value >= 1e4:
            return f"¥{value / 1e4:.0f}万"
        return f"¥{value:,.0f}"
