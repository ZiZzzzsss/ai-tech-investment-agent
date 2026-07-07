"""Mock company data for the first local research-agent prototype.

TODO: Replace these mock fixtures with real data connectors for SEC filings,
company IR pages, earnings releases, investor presentations, official macro
datasets, and licensed market data after source permissions are defined.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """A mock valuation scenario."""

    name: str
    revenue_cagr_pct: float
    terminal_margin_pct: float
    exit_multiple: float
    implied_value_per_share: float
    probability: float
    note: str


@dataclass(frozen=True)
class BayesianGrowthView:
    """Mock Bayesian intrinsic growth assumptions."""

    prior_growth_pct: float
    evidence_update_pct: float
    posterior_growth_pct: float
    confidence: str
    interpretation: str


@dataclass(frozen=True)
class TamAdjustedPegView:
    """Mock TAM-adjusted PEG inputs."""

    serviceable_tam_usd_b: float
    penetration_pct: float
    growth_duration_years: int
    conventional_peg: float
    tam_adjusted_peg: float
    interpretation: str


@dataclass(frozen=True)
class GfDmaHealthView:
    """Mock GF-DMA scorecard.

    GF-DMA is defined here as Growth, Financial quality, Demand momentum,
    Moat durability, and AI execution.
    """

    growth: int
    financial_quality: int
    demand_momentum: int
    moat_durability: int
    ai_execution: int
    trend: str
    confidence: str


@dataclass(frozen=True)
class CompanyMockData:
    """Mock company profile used by the report generator."""

    ticker: str
    name: str
    business_summary: str
    ai_exposure: str
    financial_snapshot: dict[str, str]
    valuation_multiples: dict[str, str]
    scenarios: tuple[Scenario, ...]
    bayesian_growth: BayesianGrowthView
    tam_adjusted_peg: TamAdjustedPegView
    gf_dma: GfDmaHealthView
    entry_price_framework: dict[str, str]
    macro_industry_tracker: tuple[str, ...]
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]


MOCK_COMPANIES: dict[str, CompanyMockData] = {
    "NVDA": CompanyMockData(
        ticker="NVDA",
        name="NVIDIA Corporation",
        business_summary="Mock profile: accelerated computing platform spanning GPUs, networking, systems, and software.",
        ai_exposure="Mock view: highest AI infrastructure exposure in the watchlist through data-center accelerators and ecosystem software.",
        financial_snapshot={
            "Revenue growth": "Mock high-growth profile",
            "Gross margin": "Mock premium margin profile",
            "Operating margin": "Mock high operating leverage",
            "Free cash flow": "Mock strong cash generation",
            "Balance sheet": "Mock net-cash position",
        },
        valuation_multiples={
            "EV/Sales": "Mock elevated",
            "P/E": "Mock elevated",
            "FCF yield": "Mock low-to-mid single digit",
            "Gross profit multiple": "Mock premium",
        },
        scenarios=(
            Scenario("Bear", 12.0, 42.0, 24.0, 620.0, 0.25, "AI capex digestion and multiple compression."),
            Scenario("Base", 22.0, 50.0, 34.0, 880.0, 0.50, "Sustained accelerator demand with margin normalization."),
            Scenario("Bull", 32.0, 55.0, 44.0, 1180.0, 0.25, "Platform economics expand with software and networking attach."),
        ),
        bayesian_growth=BayesianGrowthView(18.0, 6.0, 24.0, "Medium", "Mock posterior reflects strong AI evidence but recognizes cyclicality."),
        tam_adjusted_peg=TamAdjustedPegView(650.0, 18.0, 7, 1.7, 1.2, "Mock TAM adjustment improves PEG if AI infrastructure expands as assumed."),
        gf_dma=GfDmaHealthView(9, 9, 8, 9, 9, "Positive", "Medium"),
        entry_price_framework={
            "Conservative range": "Mock: below bear/base midpoint",
            "Fair range": "Mock: near scenario-weighted value",
            "Aggressive range": "Mock: requires bull-case evidence",
        },
        macro_industry_tracker=(
            "Hyperscaler capex intentions",
            "Export-control developments",
            "HBM and advanced packaging supply",
            "Enterprise AI monetization evidence",
        ),
        catalysts=(
            "Next earnings release and data-center guidance",
            "New accelerator platform ramp indicators",
            "Networking and software attach-rate disclosures",
        ),
        risks=(
            "AI capex pause or digestion cycle",
            "Customer concentration and hyperscaler bargaining power",
            "Export restrictions and supply-chain bottlenecks",
            "Valuation multiple compression",
        ),
    ),
    "AMD": CompanyMockData(
        ticker="AMD",
        name="Advanced Micro Devices, Inc.",
        business_summary="Mock profile: diversified CPU, GPU, FPGA, and adaptive computing supplier.",
        ai_exposure="Mock view: meaningful AI accelerator optionality with execution still being proven.",
        financial_snapshot={
            "Revenue growth": "Mock cyclical recovery profile",
            "Gross margin": "Mock improving margin profile",
            "Operating margin": "Mock expanding leverage",
            "Free cash flow": "Mock moderate cash generation",
            "Balance sheet": "Mock flexible balance sheet",
        },
        valuation_multiples={
            "EV/Sales": "Mock premium",
            "P/E": "Mock elevated",
            "FCF yield": "Mock modest",
            "Gross profit multiple": "Mock above-cycle average",
        },
        scenarios=(
            Scenario("Bear", 6.0, 22.0, 18.0, 88.0, 0.30, "AI ramp disappoints and PC/server cycles remain uneven."),
            Scenario("Base", 15.0, 28.0, 26.0, 135.0, 0.50, "AI GPU share gains complement CPU recovery."),
            Scenario("Bull", 24.0, 34.0, 34.0, 195.0, 0.20, "AI accelerator and adaptive compute attach accelerate."),
        ),
        bayesian_growth=BayesianGrowthView(10.0, 4.0, 14.0, "Medium", "Mock posterior rewards AI optionality but discounts execution uncertainty."),
        tam_adjusted_peg=TamAdjustedPegView(420.0, 7.0, 6, 1.9, 1.5, "Mock TAM adjustment depends on credible accelerator share gains."),
        gf_dma=GfDmaHealthView(7, 7, 6, 7, 7, "Improving", "Medium"),
        entry_price_framework={
            "Conservative range": "Mock: requires downside protection from CPU recovery alone",
            "Fair range": "Mock: near base-case execution",
            "Aggressive range": "Mock: assumes visible AI share capture",
        },
        macro_industry_tracker=(
            "Server CPU refresh cycle",
            "AI accelerator qualification pace",
            "PC demand normalization",
            "Foundry wafer availability and cost",
        ),
        catalysts=(
            "AI accelerator revenue updates",
            "Server CPU share commentary",
            "Embedded and adaptive computing stabilization",
        ),
        risks=(
            "AI product execution shortfall",
            "Competitive pressure from incumbent accelerators",
            "PC and server cycle weakness",
            "Margin dilution from ramp costs",
        ),
    ),
    "ASML": CompanyMockData(
        ticker="ASML",
        name="ASML Holding N.V.",
        business_summary="Mock profile: lithography equipment supplier central to advanced semiconductor manufacturing.",
        ai_exposure="Mock view: indirect AI exposure through advanced-node capacity and leading-edge fab investment.",
        financial_snapshot={
            "Revenue growth": "Mock equipment-cycle growth",
            "Gross margin": "Mock premium equipment margin",
            "Operating margin": "Mock strong operating leverage",
            "Free cash flow": "Mock lumpy but resilient",
            "Balance sheet": "Mock strong balance sheet",
        },
        valuation_multiples={
            "EV/Sales": "Mock premium industrial-tech multiple",
            "P/E": "Mock premium",
            "FCF yield": "Mock moderate",
            "Gross profit multiple": "Mock high-quality supplier premium",
        },
        scenarios=(
            Scenario("Bear", 4.0, 28.0, 22.0, 610.0, 0.25, "Export controls and fab delays pressure bookings."),
            Scenario("Base", 11.0, 32.0, 30.0, 825.0, 0.55, "EUV demand tracks advanced-node roadmaps."),
            Scenario("Bull", 17.0, 36.0, 36.0, 1080.0, 0.20, "High-NA adoption and AI-driven capacity pull forward demand."),
        ),
        bayesian_growth=BayesianGrowthView(9.0, 2.0, 11.0, "Medium", "Mock posterior reflects durable bottleneck status with policy risk."),
        tam_adjusted_peg=TamAdjustedPegView(210.0, 30.0, 8, 1.8, 1.4, "Mock TAM adjustment benefits from concentrated lithography economics."),
        gf_dma=GfDmaHealthView(7, 9, 7, 10, 6, "Stable", "Medium"),
        entry_price_framework={
            "Conservative range": "Mock: below equipment-cycle downside value",
            "Fair range": "Mock: near base normalized bookings",
            "Aggressive range": "Mock: assumes strong High-NA cycle",
        },
        macro_industry_tracker=(
            "Advanced-node fab spending",
            "China export-control policy",
            "Memory capital expenditure cycle",
            "Foundry utilization",
        ),
        catalysts=(
            "Order-book commentary",
            "High-NA shipment milestones",
            "Foundry and memory capex revisions",
        ),
        risks=(
            "Export restrictions",
            "Semiconductor equipment downcycle",
            "Customer concentration",
            "High valuation versus cyclical earnings",
        ),
    ),
    "TSMC": CompanyMockData(
        ticker="TSMC",
        name="Taiwan Semiconductor Manufacturing Company Limited",
        business_summary="Mock profile: leading pure-play foundry with advanced-node manufacturing scale.",
        ai_exposure="Mock view: high indirect and direct AI exposure through accelerator, CPU, and custom silicon production.",
        financial_snapshot={
            "Revenue growth": "Mock advanced-node growth",
            "Gross margin": "Mock high foundry margin",
            "Operating margin": "Mock strong scale economics",
            "Free cash flow": "Mock capex-intensive",
            "Balance sheet": "Mock strong liquidity",
        },
        valuation_multiples={
            "EV/Sales": "Mock moderate premium",
            "P/E": "Mock reasonable versus growth",
            "FCF yield": "Mock capex-cycle dependent",
            "Gross profit multiple": "Mock quality premium",
        },
        scenarios=(
            Scenario("Bear", 5.0, 34.0, 15.0, 115.0, 0.25, "Geopolitical risk and capex burden weigh on value."),
            Scenario("Base", 13.0, 40.0, 20.0, 165.0, 0.55, "AI and advanced nodes support durable growth."),
            Scenario("Bull", 20.0, 44.0, 25.0, 225.0, 0.20, "Custom AI silicon and pricing power expand returns."),
        ),
        bayesian_growth=BayesianGrowthView(10.0, 3.0, 13.0, "Medium", "Mock posterior balances AI demand with geopolitical and capex risk."),
        tam_adjusted_peg=TamAdjustedPegView(500.0, 20.0, 8, 1.3, 1.0, "Mock TAM adjustment suggests growth quality if capacity earns target returns."),
        gf_dma=GfDmaHealthView(8, 9, 8, 9, 8, "Positive", "Medium"),
        entry_price_framework={
            "Conservative range": "Mock: discounts geopolitical and capex risk",
            "Fair range": "Mock: near base advanced-node demand",
            "Aggressive range": "Mock: assumes stronger AI silicon pricing",
        },
        macro_industry_tracker=(
            "Advanced packaging capacity",
            "Customer AI chip demand",
            "Taiwan geopolitical risk indicators",
            "Global fab utilization",
        ),
        catalysts=(
            "Monthly revenue trend",
            "Advanced-node margin commentary",
            "AI customer demand updates",
        ),
        risks=(
            "Geopolitical disruption",
            "Capex intensity and depreciation pressure",
            "Customer concentration",
            "Cyclical utilization downturn",
        ),
    ),
    "ARM": CompanyMockData(
        ticker="ARM",
        name="Arm Holdings plc",
        business_summary="Mock profile: processor IP licensing and royalty platform across mobile, edge, data center, and automotive.",
        ai_exposure="Mock view: AI optionality through power-efficient CPU IP, edge inference, custom silicon, and data-center adoption.",
        financial_snapshot={
            "Revenue growth": "Mock royalty and licensing growth",
            "Gross margin": "Mock software-like margin",
            "Operating margin": "Mock scalable model",
            "Free cash flow": "Mock strong conversion potential",
            "Balance sheet": "Mock asset-light profile",
        },
        valuation_multiples={
            "EV/Sales": "Mock very elevated",
            "P/E": "Mock very elevated",
            "FCF yield": "Mock low",
            "Gross profit multiple": "Mock premium IP multiple",
        },
        scenarios=(
            Scenario("Bear", 8.0, 32.0, 25.0, 72.0, 0.30, "Royalty growth underwhelms relative to valuation."),
            Scenario("Base", 17.0, 42.0, 38.0, 112.0, 0.50, "Royalty uplift and AI edge adoption support premium."),
            Scenario("Bull", 26.0, 50.0, 52.0, 165.0, 0.20, "Data-center and custom silicon adoption expand royalty pool."),
        ),
        bayesian_growth=BayesianGrowthView(13.0, 4.0, 17.0, "Low-Medium", "Mock posterior reflects asset-light AI optionality but high valuation hurdle."),
        tam_adjusted_peg=TamAdjustedPegView(320.0, 12.0, 9, 2.5, 1.8, "Mock TAM adjustment still requires strong royalty expansion to justify premium multiples."),
        gf_dma=GfDmaHealthView(8, 8, 7, 8, 7, "Improving", "Low-Medium"),
        entry_price_framework={
            "Conservative range": "Mock: requires a large margin of safety to premium multiple",
            "Fair range": "Mock: depends on royalty growth visibility",
            "Aggressive range": "Mock: assumes data-center AI optionality converts",
        },
        macro_industry_tracker=(
            "Smartphone unit cycle",
            "Data-center CPU architecture adoption",
            "Edge AI inference demand",
            "Royalty-rate expansion evidence",
        ),
        catalysts=(
            "Royalty rate disclosures",
            "Data-center design wins",
            "Automotive and edge AI licensing updates",
        ),
        risks=(
            "Valuation already prices substantial optionality",
            "Customer insourcing or RISC-V alternatives",
            "Mobile cycle weakness",
            "Limited visibility into end-device royalty ramp",
        ),
    ),
    "NBIS": CompanyMockData(
        ticker="NBIS",
        name="Nebius Group N.V.",
        business_summary="Mock profile: AI infrastructure and cloud services platform.",
        ai_exposure="Mock view: direct AI cloud infrastructure exposure with earlier-stage execution risk.",
        financial_snapshot={
            "Revenue growth": "Mock early-stage high growth",
            "Gross margin": "Mock ramping infrastructure margin",
            "Operating margin": "Mock investment-stage losses",
            "Free cash flow": "Mock capex-consuming",
            "Balance sheet": "Mock funding-sensitive",
        },
        valuation_multiples={
            "EV/Sales": "Mock high-uncertainty",
            "P/E": "Mock not meaningful",
            "FCF yield": "Mock negative",
            "Gross profit multiple": "Mock immature",
        },
        scenarios=(
            Scenario("Bear", 10.0, -5.0, 2.0, 8.0, 0.35, "Capacity utilization disappoints and funding costs rise."),
            Scenario("Base", 28.0, 12.0, 5.0, 18.0, 0.45, "Utilization improves with controlled capex expansion."),
            Scenario("Bull", 45.0, 22.0, 8.0, 34.0, 0.20, "AI cloud demand scales and unit economics improve materially."),
        ),
        bayesian_growth=BayesianGrowthView(16.0, 5.0, 21.0, "Low", "Mock posterior recognizes direct AI exposure but discounts immature proof points."),
        tam_adjusted_peg=TamAdjustedPegView(180.0, 3.0, 6, 2.8, 2.0, "Mock TAM adjustment remains speculative until utilization and margins are proven."),
        gf_dma=GfDmaHealthView(7, 4, 6, 4, 6, "Watch", "Low"),
        entry_price_framework={
            "Conservative range": "Mock: requires evidence of funding runway and utilization",
            "Fair range": "Mock: near base unit-economics progress",
            "Aggressive range": "Mock: assumes rapid AI cloud scaling",
        },
        macro_industry_tracker=(
            "AI cloud GPU supply and lease rates",
            "Cost of capital",
            "Enterprise AI workload migration",
            "Power and data-center availability",
        ),
        catalysts=(
            "Utilization and backlog disclosure",
            "Funding or partnership announcements",
            "Gross margin progression",
        ),
        risks=(
            "Execution and funding risk",
            "GPU cloud pricing pressure",
            "Capex intensity",
            "Limited operating history as a public AI infrastructure story",
        ),
    ),
}


ALIASES = {"NEBIUS": "NBIS"}


def available_tickers() -> tuple[str, ...]:
    """Return supported mock tickers."""

    return tuple(sorted(MOCK_COMPANIES))


def get_mock_company(ticker: str) -> CompanyMockData:
    """Load mock company data by ticker."""

    normalized = ticker.strip().upper()
    normalized = ALIASES.get(normalized, normalized)
    try:
        return MOCK_COMPANIES[normalized]
    except KeyError as exc:
        supported = ", ".join(available_tickers())
        raise ValueError(f"Unsupported ticker '{ticker}'. Supported mock tickers: {supported}") from exc
