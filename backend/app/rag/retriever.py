"""
SmartCycle — Hybrid Retriever
===============================

Combines dense (semantic) and sparse (keyword) retrieval with
Weighted Reciprocal Rank Fusion (WRRF) for robust document ranking.

Architecture:
  1. Dense pass:  embed(query) → vector_store.search()
  2. Sparse pass: keyword overlap scoring (BM25-style)
  3. Fusion:      merge with weighted reciprocal rank

Compatible with Python 3.9+ — no PEP 604 union syntax.
"""

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger("smartcycle.rag.retriever")

# ═══════════════════════════════════════════════════════════════
# Financial Document Corpus (mock knowledge base)
# ═══════════════════════════════════════════════════════════════
# This is the initial document set. In production, documents are
# ingested from files, APIs, or databases via ingest.py.

_DEFAULT_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "doc_pboc_2024q3",
        "title": "PBOC Q3 2024 Monetary Policy Report",
        "source": "People's Bank of China",
        "date": "2024-11-08",
        "snippet": "The PBOC maintained a prudent monetary policy with targeted RRR cuts for small and micro enterprises. The 1-year LPR stands at 3.10% and the 5-year LPR at 3.60%. M2 money supply grew 6.8% YoY. The central bank signaled continued support for the real economy through structural monetary tools.",
        "keywords": ["PBOC", "monetary policy", "RRR", "LPR", "interest rate", "M2", "央行", "货币政策", "降准"],
        "category": "macro",
    },
    {
        "id": "doc_csrc_compliance",
        "title": "CSRC Compliance Guidelines for AI-Generated Financial Content",
        "source": "China Securities Regulatory Commission",
        "date": "2024-09-15",
        "snippet": "All AI-generated financial advisory content must include risk disclaimers. Any promise of absolute returns or claims of zero-risk investment constitutes a violation of Article 77 of the Securities Law. Financial advisors remain legally responsible for AI-assisted outputs. Mandatory disclosure: 'Past performance does not guarantee future results.'",
        "keywords": ["CSRC", "compliance", "AI regulation", "risk disclosure", "证监会", "合规", "风险披露"],
        "category": "regulation",
    },
    {
        "id": "doc_ev_battery_2024",
        "title": "EV Battery Supply Chain Analysis 2024",
        "source": "CITIC Securities Research",
        "date": "2024-10-20",
        "snippet": "Lithium carbonate prices stabilized at ¥95,000-110,000/ton after a 70% decline from 2022 peaks. CATL maintains 37% global market share. Overcapacity in LFP cathode production is pressuring margins. Solid-state battery commercialization expected post-2027. Key players: CATL (300750), BYD (002594), Gotion (002074), CALB (03931.HK).",
        "keywords": ["EV", "battery", "lithium", "CATL", "BYD", "新能源", "锂电池", "宁德时代", "比亚迪"],
        "category": "sector",
    },
    {
        "id": "doc_csi300_rotation",
        "title": "CSI 300 Sector Rotation Strategy — H2 2024",
        "source": "China International Capital Corporation (CICC)",
        "date": "2024-07-01",
        "snippet": "Defensive sectors (consumer staples, healthcare) outperformed cyclicals in H1 2024. Recommend overweight: healthcare (PE 28x, below 5-year median), consumer staples (Moutai at attractive valuation). Underweight: real estate, materials. CSI 300 forward P/E is 11.8x vs 5-year average of 13.2x, suggesting moderate undervaluation.",
        "keywords": ["CSI 300", "sector rotation", "沪深300", "板块轮动", "估值", "valuation", "consumer staples"],
        "category": "strategy",
    },
    {
        "id": "doc_sse_investor_edu",
        "title": "SSE Investor Education: Understanding Market Volatility",
        "source": "Shanghai Stock Exchange",
        "date": "2024-06-01",
        "snippet": "Market corrections of 10-20% occur on average every 2-3 years in A-shares. Long-term investors (5+ year horizon) in the CSI 300 have historically achieved 7-9% annualized returns. Dollar-cost averaging reduces timing risk. Panic selling during corrections typically locks in losses. Diversification across 3+ sectors reduces portfolio volatility by 30-40%.",
        "keywords": ["investor education", "volatility", "长期投资", "定投", "分散化", "波动", "投资者教育"],
        "category": "education",
    },
    {
        "id": "doc_fund_flows_q2",
        "title": "Q2 2024 Mutual Fund Flow Analysis",
        "source": "China Asset Management Association",
        "date": "2024-08-15",
        "snippet": "Equity mutual funds saw net outflows of ¥180B in Q2 2024, while bond funds attracted ¥350B in net inflows — signaling risk-off sentiment among retail investors. ETFs bucked the trend with ¥95B net inflows, dominated by CSI 300 ETF (510300) and STAR 50 ETF (588000). Northbound connect saw ¥42B net inflow, concentrated in consumer and new energy sectors.",
        "keywords": ["mutual fund", "ETF", "flow", "基金", "资金流向", "北向资金", "CSI 300 ETF"],
        "category": "flow",
    },
    {
        "id": "doc_fintech_ai_trends",
        "title": "AI in Wealth Management: 2024 Landscape",
        "source": "McKinsey & Company",
        "date": "2024-05-22",
        "snippet": "AI-powered wealth management platforms are projected to manage $6T in AUM globally by 2027. Key trends: (1) Hyper-personalization via LLMs — portfolio advice tailored to individual risk profiles and life stages; (2) Compliance automation — reducing manual review costs by 60-80%; (3) Multi-agent systems for complex financial reasoning. Chinese fintech leads in AI adoption rate at 78% vs global 52%.",
        "keywords": ["fintech", "AI", "wealth management", "金融科技", "智能投顾", "robo-advisor"],
        "category": "industry",
    },
    {
        "id": "doc_csi_500_outlook",
        "title": "CSI 500 Mid-Cap Outlook — 2025 Strategy",
        "source": "Huatai Securities Research",
        "date": "2024-12-01",
        "snippet": "CSI 500 constituents (mid-cap, avg market cap ¥22B) trade at 18.2x forward P/E, below the 10-year median of 22.5x. Key themes for 2025: (1) AI semiconductor supply chain localization; (2) Commercial aerospace — satellite internet constellation buildout; (3) Biotech innovation — ADC drugs and CAR-T. Top picks: NAURA (002371), Hygeia (300896), iFLYTEK (002230).",
        "keywords": ["CSI 500", "中证500", "mid-cap", "semiconductor", "半导体", "biotech"],
        "category": "strategy",
    },
    {
        "id": "doc_bond_market_review",
        "title": "China Bond Market Review & 2025 Rate Outlook",
        "source": "ChinaBond Pricing Center",
        "date": "2024-12-10",
        "snippet": "China 10-year government bond yield fell to 1.70% in December 2024, a historic low, reflecting accommodative monetary policy and weak inflation expectations. Corporate bond default rate declined to 0.38% (vs 0.61% in 2023). Convertible bonds offer attractive risk-reward with average conversion premium at 28%. LGFV bond spreads compressed 40bp as restructuring plans advanced.",
        "keywords": ["bond", "债券", "yield", "收益率", "interest rate", "利率", "LGFV", "城投债"],
        "category": "macro",
    },
    {
        "id": "doc_realestate_policy",
        "title": "Real Estate Policy Easing — Impact Assessment",
        "source": "China Index Academy",
        "date": "2024-11-20",
        "snippet": "The September 2024 policy package (down payment ratio cut to 15%, mortgage rate floor removal, whitelist project expansion) has stabilized transaction volumes in Tier-1 cities. Home sales in Shanghai rose 35% MoM in October. Developers' financing pressure remains acute — aggregate bond maturities of ¥280B due in 2025. Policy transmission to new home starts remains weak. Property sector weighting in CSI 300 fell from 9.2% to 5.1%.",
        "keywords": ["real estate", "房地产", "policy", "政策", "mortgage", "房贷", "developer", "开发商"],
        "category": "sector",
    },
    {
        "id": "doc_quant_trading_regulation",
        "title": "Quantitative Trading Regulatory Framework Update",
        "source": "CSRC / AMAC Joint Notice",
        "date": "2024-10-08",
        "snippet": "New quant trading reporting requirements effective January 2025: (1) All programmatic trading accounts must register with exchanges; (2) Order-to-trade ratio capped at 300:1 per account per day; (3) Minimum resting time of 50ms for market orders; (4) Abnormal return monitoring threshold set at 3 standard deviations from sector mean. Exemptions for market-making and liquidity provision programs. Penalties for non-compliance include trading suspension and fines up to ¥5M.",
        "keywords": ["quantitative trading", "量化交易", "regulation", "监管", "programmatic", "程序化交易"],
        "category": "regulation",
    },
    {
        "id": "doc_greenfinance_cbam",
        "title": "Green Finance & EU CBAM Implications for Chinese Exporters",
        "source": "Industrial Bank Green Finance Research",
        "date": "2024-11-15",
        "snippet": "EU Carbon Border Adjustment Mechanism (CBAM) transitional phase began October 2023 with full implementation by 2026. Chinese steel and aluminum exporters face additional costs of 4-8% of export value. Green bond issuance in China reached ¥1.2T in 2024 (+35% YoY). Carbon trading price on the national ETS stabilized at ¥75-85/ton CO2. Transition finance products (SLB, transition bonds) grew 120% YoY. Key beneficiaries: carbon verification agencies, green certification firms, and low-carbon tech providers.",
        "keywords": ["green finance", "绿色金融", "CBAM", "carbon", "碳交易", "ESG", "sustainable"],
        "category": "industry",
    },
    {
        "id": "doc_retirement_pillar3",
        "title": "Pillar 3 Private Pension — One Year Review",
        "source": "National Financial Regulatory Administration (NFRA)",
        "date": "2024-12-05",
        "snippet": "China's private pension pilot (Pillar 3) enrolled 60M+ participants in its first year with ¥42B in contributions. Average annual contribution: ¥7,000 per participant (well below the ¥12,000 cap). 78% of accounts chose deposit products; only 12% selected mutual funds and 6% chose insurance products. Target-date pension FOFs (fund-of-funds) delivered average 2.3% return in 2024 vs 1.8% for deposits. Policy tailwind: expansion to all 31 provinces in 2025, potential increase of contribution cap to ¥18,000.",
        "keywords": ["pension", "养老金", "Pillar 3", "第三支柱", "retirement", "养老", "FOF"],
        "category": "policy",
    },
    {
        "id": "doc_onshore_offshore_spread",
        "title": "A-H Share Premium Analysis — Cross-Border Arbitrage Dynamics",
        "source": "Goldman Sachs China Strategy",
        "date": "2024-12-12",
        "snippet": "The Hang Seng AH Premium Index hovered at 142-148 in Q4 2024, meaning A-shares trade at a 42-48% premium to their H-share counterparts on average. Sectors with widest premium: financials (52%), materials (48%), industrials (45%). Narrowest: consumer discretionary (18%), healthcare (22%). Southbound connect net inflows reached ¥420B YTD, concentrated in high-dividend SOEs (China Mobile, CNOOC, ICBC). Cross-border arbitrage strategies face execution risk from quota limits and FX hedging costs (3.2% annualized for CNH).",
        "keywords": ["AH premium", "A股H股", "arbitrage", "套利", "southbound", "港股通", "cross-border"],
        "category": "strategy",
    },
    {
        "id": "doc_us_china_tech_decoupling",
        "title": "US-China Technology Decoupling — Semiconductor Sector Impact",
        "source": "Semiconductor Industry Association / CSIA",
        "date": "2024-10-25",
        "snippet": "October 2024 US export controls expanded restrictions on advanced node semiconductor equipment (sub-14nm logic, sub-18nm DRAM, sub-128-layer NAND). Chinese semiconductor equipment localization rate rose from 7% (2018) to 25% (2024). SMIC's 7nm (N+2) process achieved low-volume production for Huawei Ascend AI chips. Equipment leaders: AMEC (688012) in etching, Naura (002371) in deposition, Advanced Micro-Fabrication (688012) in CVD. EDA tool self-sufficiency rose to estimated 15%. The 'choke point' remains lithography — domestic immersion DUV tools (SMEE) at 90nm resolution vs ASML's 13.5nm EUV.",
        "keywords": ["semiconductor", "半导体", "chip", "芯片", "decoupling", "脱钩", "SMIC", "中芯国际", "Huawei"],
        "category": "sector",
    },
    # ══════════════════════════════════════════════════════════════
    # Phase 8 Expansion — 2025-2026 Documents (15 new)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "doc_deepseek_ai_impact_2025",
        "title": "DeepSeek Moment — AI Disruption Reshapes Chinese Tech Valuations",
        "source": "Goldman Sachs / CITIC Securities",
        "date": "2026-03-15",
        "snippet": "The emergence of DeepSeek-R1 in January 2025, achieving GPT-4-class performance at an estimated 95% lower training cost, triggered a fundamental re-rating of Chinese tech stocks. The STAR 50 Index rose 38% in Q1 2025 alone. Key implications: (1) AI democratization — smaller players can now compete, compressing incumbents' moat; (2) Hardware demand shift — inference chip demand growing 3x faster than training; (3) Software/AI application layer benefiting disproportionately — iFLYTEK, Kingsoft Office, and Meituan's AI features driving user growth. The CSI信息技术 Index trades at 35x forward P/E vs 22x pre-DeepSeek, suggesting structural rather than cyclical re-rating.",
        "keywords": ["DeepSeek", "AI", "deepseek", "STAR 50", "科创板", "tech valuation", "AI democratization", "inference"],
        "category": "sector",
    },
    {
        "id": "doc_healthcare_aging_2026",
        "title": "China Healthcare — Silver Economy & Innovation Drug Boom",
        "source": "CICC Research / Deloitte Life Sciences",
        "date": "2026-05-20",
        "snippet": "China's healthcare expenditure reached 7.4% of GDP in 2025, driven by the 310M-strong 60+ population. Innovative drug NDA approvals hit a record 52 in 2025, with 15 receiving FDA breakthrough designation — up from 12 in 2024. Key trends: (1) ADC (antibody-drug conjugate) out-licensing deals totaled $28B in 2025, making China the largest ADC IP exporter globally; (2) Medical device localization in high-end imaging (CT, MRI, endoscopy) reached 48%; (3) TCM modernization attracting policy support with ¥50B allocated for TCM digitalization and evidence-based validation. Hospital chain operators (Aier Eye, Tongce Medical) benefit from consumption upgrade in lower-tier cities.",
        "keywords": ["healthcare", "医药", "pharma", "aging", "老龄化", "ADC", "medical device", "医疗器械", "TCM", "中药"],
        "category": "sector",
    },
    {
        "id": "doc_baijiu_consumer_2026",
        "title": "Baijiu & Premium Consumer — Structural Downturn or Cyclical Bottom?",
        "source": "Huatai Securities Consumer Research",
        "date": "2026-06-10",
        "snippet": "The baijiu sector faces its most severe demand contraction in a decade. Kweichow Moutai's wholesale Feitian price declined from ¥2,700 (2024 peak) to ¥2,180 (June 2026), while guidance was cut to 8% revenue growth (vs 15% historical CAGR). Key headwinds: (1) Banquet/banquet consumption down 25% from pre-COVID levels; (2) Youth consumer preference shifting to low-alcohol and RTD beverages; (3) De-stocking cycle — channel inventory at 4.2 months vs normal 2.5 months. However, bulls argue: (a) Moutai at 28x P/E is near 10-year low; (b) International expansion potential — Moutai export revenue grew 42% YoY; (c) Premiumization of mass-market brands (Fenjiu, Gujing) creating new growth tiers. The sector is a proxy for China's consumption confidence.",
        "keywords": ["baijiu", "白酒", "Moutai", "茅台", "consumer", "消费", "premium", "consumption downgrade"],
        "category": "sector",
    },
    {
        "id": "doc_gold_commodities_2026",
        "title": "Gold, Copper & Critical Minerals — Commodity Supercycle Check",
        "source": "World Gold Council / SMM / LME",
        "date": "2026-07-01",
        "snippet": "Gold at $2,580/oz (+18% YTD) driven by: PBOC gold reserves up to 2,350 tons (continuing 18-month buying streak), de-dollarization reserve diversification by BRICS+ central banks, and real yield compression as global inflation stays sticky at 2.5-3.0%. Copper at $9,800/ton — green transition demand (EVs, grid, renewables) adds 2.5% annual demand growth vs 1.8% supply growth, pointing to structural deficit by 2028. Lithium carbonate stabilized at ¥95,000-100,000/ton as marginal producers cut output. Rare earths — China export controls on medium/heavy rare earths (March 2026) pushed dysprosium and terbium prices up 35%, benefiting Northern Rare Earth (600111). Critical mineral supply chain diversification is the defining commodity theme of the decade.",
        "keywords": ["gold", "黄金", "copper", "铜", "lithium", "锂", "commodity", "大宗商品", "rare earth", "稀土", "PBOC gold"],
        "category": "macro",
    },
    {
        "id": "doc_star_market_2026",
        "title": "STAR Market 科创板 — Seven-Year Review & Ecosystem Maturation",
        "source": "Shanghai Stock Exchange / CSRC",
        "date": "2026-06-13",
        "snippet": "As the STAR Market approaches its 7th anniversary (launched July 2019): 630+ listed companies with ¥8.2T combined market cap; 78% are in 'hard tech' sectors (semiconductor, biotech, AI, advanced manufacturing). Key metrics: (1) Average R&D intensity 12.5% of revenue vs 3.2% for main board — highest among all Chinese boards; (2) IPO pipeline healthy with 120+ filings in review, median time-to-list reduced to 8 months; (3) Market-making program expanded to 280 stocks, reducing bid-ask spreads by 35%; (4) STAR 50 Index constituents being included in MSCI and FTSE indices, attracting passive foreign inflows. Challenges remain: high valuation volatility (average 60-day realized vol 32% vs CSI 300's 18%), limited analyst coverage for small-caps, and retail-dominated trading (retail volume share 62%).",
        "keywords": ["STAR Market", "科创板", "Kechuang", "technology", "IPO", "R&D", "hard tech", "科创50"],
        "category": "strategy",
    },
    {
        "id": "doc_fed_global_macro_2026",
        "title": "Federal Reserve & Global Monetary Policy Divergence — H2 2026",
        "source": "IMF World Economic Outlook / BIS",
        "date": "2026-07-10",
        "snippet": "The Fed holds at 3.25-3.50% while ECB cut to 2.25% and BOJ raised to 0.75% — the most significant G3 policy divergence since 2008. PBOC maintains accommodative stance with 1Y MLF at 2.30%. Implications for Chinese investors: (1) Narrowing CNH-USD rate differential (-145bp) limits room for aggressive PBOC easing without triggering capital outflows; (2) Weaker DXY (100.2) supportive for EM assets — MSCI China has rallied 22% YTD in USD terms; (3) Global bond correlation breaking down — China government bonds increasingly trade on domestic factors (CPI, credit impulse) rather than tracking USTs. IMF projects global growth of 3.2% in 2026 with China contributing 35% of global growth.",
        "keywords": ["Fed", "美联储", "ECB", "monetary policy", "global macro", "interest rate", "CNH", "DXY", "IMF"],
        "category": "macro",
    },
    {
        "id": "doc_digital_yuan_2026",
        "title": "Digital Yuan (e-CNY) — Phase 3 Expansion & Cross-Border Pilots",
        "source": "PBOC Digital Currency Research Institute",
        "date": "2026-04-20",
        "snippet": "e-CNY transaction volume reached ¥4.2T cumulatively with 320M individual wallets opened. Phase 3 (2026) key initiatives: (1) Cross-border — mBridge platform (BIS + PBOC + HKMA + Bank of Thailand + UAE Central Bank) processing ¥120B in live wholesale CBDC transactions; (2) Smart contract programmable payments — government subsidies, supply chain finance, and carbon credit settlement now running on e-CNY rails; (3) Integration with WeChat Pay and Alipay — e-CNY now appears as a payment option in both super-apps. Key beneficiaries: banks providing e-CNY infrastructure (ICBC, CCB, BOC), fintechs building programmable payment solutions, and hardware wallet manufacturers. Privacy-enhanced e-CNY (可控匿名) with selective disclosure remains the design principle distinguishing it from fully traceable alternatives.",
        "keywords": ["digital yuan", "数字人民币", "e-CNY", "CBDC", "mBridge", "cross-border", "payment", "央行数字货币"],
        "category": "industry",
    },
    {
        "id": "doc_portfolio_risk_management",
        "title": "Portfolio Risk Management — Beyond Mean-Variance Optimization",
        "source": "CFA Institute Research Foundation / SAIF",
        "date": "2026-01-15",
        "snippet": "Modern multi-asset portfolio construction requires tools beyond traditional mean-variance optimization, which is notoriously sensitive to return assumptions (estimation error can reduce out-of-sample Sharpe by 40-60%). Recommended framework: (1) Risk parity — equal risk contribution from each asset class, more robust to estimation errors; (2) Black-Litterman — Bayesian blending of equilibrium returns with investor views; (3) Factor-based allocation — target exposures to value, momentum, quality, carry, and low-volatility factors. For Chinese portfolios specifically: include CNH/USD FX risk as a first-class risk factor (not residual); account for policy-event risk through scenario analysis; and use CSI 500 futures (launched 2022) and CSI 1000 options (launched 2023) for hedging mid/small-cap exposure. The Sortino ratio (focusing on downside deviation) is often more relevant than Sharpe for Chinese equities given positive skew in recovery periods.",
        "keywords": ["risk management", "风险管理", "portfolio", "Sharpe", "夏普比率", "risk parity", "Black-Litterman", "factor"],
        "category": "education",
    },
    {
        "id": "doc_us_stock_outlook_2026",
        "title": "US Equity Market — Concentration Risk & AI Hype Cycle Check",
        "source": "Morgan Stanley / Goldman Sachs US Equity Strategy",
        "date": "2026-07-08",
        "snippet": "The 'Magnificent 7' (AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA) now represent 33% of S&P 500 market cap — the highest concentration since the Nifty Fifty era. S&P 500 forward P/E of 22.5x is above the 20-year average of 16.5x but justified by higher margins and AI-driven productivity expectations. Key risks: (1) AI CapEx ROI — Big Tech's combined $280B annual CapEx requires eventual revenue payoff; (2) Regulatory — EU AI Act enforcement and potential US digital competition bill; (3) Valuation — S&P 500 equity risk premium at 2.8%, the lowest since 2007, leaving little cushion for disappointment. For Chinese investors, US exposure via QDII funds and southbound Stock Connect (HK-listed US exposure via Tracker Fund) provides diversification but carries FX and geopolitical tail risk.",
        "keywords": ["US stocks", "美股", "S&P 500", "Magnificent 7", "AI hype", "concentration", "valuation", "QDII"],
        "category": "strategy",
    },
    {
        "id": "doc_convertible_bonds_2026",
        "title": "China Convertible Bonds — Asymmetric Risk-Reward in Late Cycle",
        "source": "ChinaBond / CICC FICC Research",
        "date": "2026-06-28",
        "snippet": "China's convertible bond market has grown to ¥1.2T outstanding across 580+ issues, becoming an important asset class for institutional and retail investors. Current environment: (1) Average conversion premium at 32% (above 5-year median of 25%), reflecting equity market uncertainty; (2) Yield-to-maturity on balanced CBs (平價/平衡型) at 1.8-2.5% — providing reasonable bond floor; (3) Sector concentration — banks and financials represent 38% of total market cap, implying high correlation with financial sector beta. Strategy recommendations: favor balanced CBs with credit quality AA+ and above, conversion premium below 25%, and positive equity momentum in underlying. Avoid deep-in-the-money CBs (delta > 0.8) where the bond floor is negligible — these are essentially expensive equity proxies. The asset class is particularly suited for risk-averse investors seeking equity exposure with principal protection.",
        "keywords": ["convertible bond", "可转债", "CB", "asymmetric", "bond floor", "conversion premium", "转股溢价率"],
        "category": "strategy",
    },
    {
        "id": "doc_banking_sector_nim_2026",
        "title": "China Banking Sector — NIM Compression & Dividend Sustainability",
        "source": "CICC Banking Research / PBOC Financial Stability Report",
        "date": "2026-05-15",
        "snippet": "Chinese banks' net interest margin (NIM) compressed to a historic low of 1.45% in Q1 2026 (vs 1.68% in 2024), driven by LPR cuts and mortgage rate repricing. However, asset quality is improving: NPL ratio declined to 1.52% from 1.62% in 2024, with the property NPL formation cycle peaking. Big 4 banks (ICBC, CCB, BOC, ABC) maintain 5-6% dividend yields with 30% payout ratios — sustainable given 11-12% CET1 capital ratios. Key differentiation: wealth management fees and treasury income now contribute 25-35% of revenue at CMB and Ping An Bank vs 15-20% at SOE banks — the fee-income diversification premium justifies higher P/B multiples. For income-oriented investors, large bank A-shares and their H-share counterparts (trading at 20-25% discount) offer a rare combination of high dividend yield, improving asset quality, and policy backstop.",
        "keywords": ["banking", "银行", "NIM", "净息差", "NPL", "不良贷款", "dividend", "股息", "CMB", "招商银行"],
        "category": "sector",
    },
    {
        "id": "doc_market_microstructure_2026",
        "title": "A-Share Market Microstructure — What Retail Investors Should Know",
        "source": "Shanghai Stock Exchange / Shenzhen Stock Exchange",
        "date": "2026-03-01",
        "snippet": "Understanding A-share market mechanics is essential for informed investing: (1) T+1 settlement — shares bought today can only be sold tomorrow (unlike T+0 in US/HK), which affects intraday risk management; (2) Price limits — ±10% for main board stocks (±20% for ChiNext/STAR), with circuit breakers at index level; (3) Lot size — 100 shares per lot, with odd-lot orders (零股) allowed for selling only; (4) Auction mechanisms — opening call auction (9:15-9:25), continuous auction (9:30-11:30, 13:00-15:00), closing call auction (Shenzhen only, 14:57-15:00); (5) Market maker program on STAR Market — 280 stocks have designated market makers providing continuous two-sided quotes, reducing bid-ask spreads by 35%. The CSI A-Share Discretionary Index (888013) tracks trading costs including commissions, stamp duty (0.05% on sells only, halved in Aug 2024), and market impact — average total cost is 18bp for large-caps and 35bp for small-caps.",
        "keywords": ["market microstructure", "市场机制", "T+1", "price limit", "涨跌停", "auction", "竞价", "market maker", "stamp duty"],
        "category": "education",
    },
    {
        "id": "doc_defense_sector_2026",
        "title": "China Defense Sector — Procurement Cycle & Civil-Military Fusion",
        "source": "AVIC Securities / State Administration of Science, Technology and Industry for National Defense",
        "date": "2026-06-05",
        "snippet": "China's 2026 defense budget rose 7.2% to ¥1.78T, maintaining the multi-year trend of GDP+ growth. Key investment themes: (1) Aero-engine — domestic WS-15 entering mass production for J-20, WS-20 for Y-20, benefiting AECC Aviation Power (600893) and its supply chain; (2) Precision-guided munitions — PLA restructuring towards long-range precision strike capability, driving demand for inertial navigation, seekers, and solid rocket motors; (3) C4ISR & electronic warfare — CEC and CETC groups' listed arms benefiting from battlefield digitization; (4) Civil-military fusion (军民融合) — dual-use technologies in satellite internet, commercial aerospace, and cybersecurity attracting private capital. Valuation: defense sector average P/E of 52x reflects growth premium, but earnings visibility is unusually high given multi-year procurement contracts (typically 3-5 year orders with milestone payments). Key risk: defense procurement is opaque and politically driven — order timing can shift significantly between quarters.",
        "keywords": ["defense", "军工", "military", "aero-engine", "航空发动机", "J-20", "procurement", "军民融合"],
        "category": "sector",
    },
    {
        "id": "doc_technical_analysis_primer",
        "title": "Technical Analysis in A-Share Markets — Tools, Patterns & Limitations",
        "source": "Shenzhen Stock Exchange Investor Education / Bloomberg",
        "date": "2026-02-20",
        "snippet": "Technical analysis (技术分析) is widely used in A-share markets where retail investors represent ~60% of trading volume — making sentiment and technical patterns more self-fulfilling than in institution-dominated markets. Commonly used tools: (1) Moving averages — 20-day MA (short-term trend), 60-day MA (中期趋势, commonly watched by institutional traders), 250-day MA (年线, bull/bear demarcation); (2) Volume-price analysis — 放量上涨 (rising on high volume) is considered bullish confirmation, while 缩量下跌 (declining on low volume) suggests selling exhaustion; (3) MACD and RSI — most widely used oscillators, with RSI < 30 considered 'oversold' and RSI > 70 'overbought', though mean-reversion works better in range-bound markets than trending ones. Important caveats: (a) Technical analysis has no predictive power for event-driven moves (policy announcements, earnings surprises); (b) In highly manipulated small-caps (市值<¥5B), technical patterns are unreliable; (c) The best use of technicals is risk management (setting stop-losses) rather than entry timing.",
        "keywords": ["technical analysis", "技术分析", "MACD", "RSI", "moving average", "均线", "volume", "成交量", "candlestick"],
        "category": "education",
    },
    {
        "id": "doc_etf_ecosystem_2026",
        "title": "China ETF Ecosystem — Product Innovation & Factor Investing",
        "source": "Shanghai Stock Exchange / China Asset Management Association",
        "date": "2026-07-10",
        "snippet": "China's ETF market surpassed ¥4.2T AUM across 1,100+ products in mid-2026, growing at a 35% CAGR since 2023. Key trends: (1) Broad-base ETFs dominate — CSI 300 ETF (510300) at ¥185B AUM, SSE 50 ETF (510050) at ¥58B, CSI 500 ETF (510500) at ¥42B; (2) Sector/thematic ETFs proliferating — semiconductor ETF (512480), new energy vehicle ETF (515030), healthcare ETF (512170), AI & big data ETF (516000), and military industry ETF (512660) each surpassing ¥10B AUM; (3) Factor ETFs emerging — dividend ETF (512890, tracking CSI Dividend Index yielding 5.2%), low-volatility ETF, and quality factor ETF launched in 2025; (4) Bond ETFs growing rapidly — ¥680B AUM as investors seek fixed-income beta at lower cost than active bond funds (average expense ratio 15bp vs 60bp for active). For retail investors, ETFs solve three pain points: diversification (one trade = basket), transparency (daily holdings disclosure), and cost (management fees ~0.15-0.50%). The rise of ETF-based model portfolios (ETF投顾组合) is the next frontier.",
        "keywords": ["ETF", "交易型开放式指数基金", "index fund", "指数基金", "factor investing", "factor", "dividend", "红利"],
        "category": "education",
    },
]


# ═══════════════════════════════════════════════════════════════
# Hybrid Retriever
# ═══════════════════════════════════════════════════════════════

class HybridRetriever:
    """Hybrid dense + sparse document retrieval.

    Dense: semantic similarity via embedding cosine distance.
    Sparse: keyword overlap scoring (BM25-inspired TF-IDF approximation).
    Fusion: Weighted Reciprocal Rank Fusion (WRRF).

    Usage:
        retriever = HybridRetriever()
        results = retriever.retrieve("沪深300 估值水平", top_k=5)
        # → List of {id, title, source, snippet, score, dense_score, sparse_score}
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._vs = vector_store or get_vector_store()
        self._emb = embedding_provider or get_embedding_provider()
        self._docs = documents or _DEFAULT_DOCUMENTS

        # Index documents into vector store on first use
        self._indexed = self._vs.count() > 0
        if not self._indexed and self._docs:
            self._index_documents()

        logger.info("[rag.retriever] HybridRetriever ready (%d docs indexed)", self._vs.count())

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve documents using hybrid search.

        Args:
            query: Search query text (Chinese or English).
            top_k: Number of results to return.

        Returns:
            List of result dicts with keys: id, title, source, date, snippet,
            score (fused), dense_score, sparse_score, category, keywords.
        """
        if not query or not query.strip():
            return self._docs[:top_k] if self._docs else []

        # ── Dense retrieval ──
        q_emb = self._emb.embed(query)
        dense_results = self._vs.search(q_emb, top_k=min(top_k * 2, self._vs.count()))

        # Build dense score lookup
        dense_scores: Dict[str, float] = {}
        for r in dense_results:
            dense_scores[r["id"]] = r["score"]

        # ── Sparse retrieval (keyword scoring) ──
        sparse_scored = self._sparse_search(query, top_k=min(top_k * 2, len(self._docs)))
        sparse_scores: Dict[str, float] = {}
        for doc_id, score in sparse_scored:
            sparse_scores[doc_id] = score

        # ── Reciprocal Rank Fusion ──
        all_ids = set(list(dense_scores.keys()) + list(sparse_scores.keys()))
        fused: List[Tuple[str, float, float, float]] = []  # (id, fused, dense, sparse)

        for doc_id in all_ids:
            d_score = dense_scores.get(doc_id, 0.0)
            s_score = sparse_scores.get(doc_id, 0.0)
            fused_score = 0.6 * d_score + 0.4 * s_score  # WRRF: dense weighted higher
            fused.append((doc_id, fused_score, d_score, s_score))

        fused.sort(key=lambda x: x[1], reverse=True)

        # ── Build result dicts ──
        doc_lookup = {d["id"]: d for d in self._docs}
        results = []
        for doc_id, fused_score, d_score, s_score in fused[:top_k]:
            doc = doc_lookup.get(doc_id, {})
            results.append({
                "id": doc_id,
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "date": doc.get("date", ""),
                "snippet": doc.get("snippet", ""),
                "category": doc.get("category", ""),
                "keywords": doc.get("keywords", []),
                "score": round(fused_score, 4),
                "dense_score": round(d_score, 4),
                "sparse_score": round(s_score, 4),
            })

        return results

    # ── Internal ────────────────────────────────────────────

    def _index_documents(self) -> None:
        """Index all default documents into the vector store."""
        if not self._docs:
            return
        texts = [d["snippet"] for d in self._docs]
        ids = [d["id"] for d in self._docs]
        metadatas = [{"title": d["title"], "source": d["source"], "category": d.get("category", "")} for d in self._docs]
        embeddings = self._emb.embed_batch(texts)
        self._vs.add(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
        self._indexed = True
        logger.info("[rag.retriever] Indexed %d documents into vector store", len(self._docs))

    def _sparse_search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Keyword-based sparse retrieval with BM25-inspired scoring.

        Scores documents by:
          1. Keyword overlap between query terms and document keywords
          2. Term frequency in snippet text
          3. Document length normalization
        """
        # Tokenize query
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return [(d["id"], 0.0) for d in self._docs[:top_k]]

        scored = []
        for doc in self._docs:
            # Combine all searchable text
            doc_text = doc.get("snippet", "") + " " + " ".join(doc.get("keywords", []))
            doc_tokens = self._tokenize(doc_text)

            # Keyword overlap score
            keyword_hits = sum(1 for qt in query_tokens if any(qt in kw.lower() for kw in doc.get("keywords", [])))
            keyword_score = keyword_hits / max(len(query_tokens), 1)

            # Term frequency score
            tf_score = 0.0
            for qt in query_tokens:
                tf = sum(1 for dt in doc_tokens if qt in dt)
                if tf > 0:
                    # BM25-inspired: log-scaled term frequency
                    tf_score += math.log(1 + tf)

            # Length normalization
            doc_len = max(len(doc_tokens), 1)
            tf_score /= math.sqrt(doc_len)

            # Combined sparse score
            sparse_score = 0.5 * keyword_score + 0.5 * min(tf_score / 3.0, 1.0)
            scored.append((doc["id"], round(sparse_score, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple tokenizer for Chinese + English mixed text.

        Splits on CJK character boundaries + whitespace for English words.
        """
        tokens: List[str] = []
        # Extract Chinese characters individually
        cjk_chars = re.findall(r'[一-鿿]', text)
        tokens.extend(cjk_chars)
        # Extract English/alpha words (lowercased)
        alpha_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        tokens.extend(alpha_words)
        # Extract numbers
        numbers = re.findall(r'\d+', text)
        tokens.extend(numbers)
        return tokens


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

_retriever: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    """Return the singleton HybridRetriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
