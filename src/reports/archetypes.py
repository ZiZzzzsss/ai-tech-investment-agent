"""Company archetype profiles for mock report generation.

Archetypes customize the report framing and mock model inputs without hardcoding
every behavior directly into the Markdown renderer.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.connectors.mock_data import CompanyMockData


@dataclass(frozen=True)
class CompanyArchetypeProfile:
    """Configuration for one company archetype."""

    key: str
    display_name: str
    investment_view: str
    bayesian_revenue_weight: float
    bayesian_margin_weight: float
    bayesian_fcf_weight: float
    bayesian_backlog_weight: float
    bayesian_hyperscaler_weight: float
    bayesian_ai_exposure_weight: float
    gf_dma_revenue_weight: float
    gf_dma_eps_weight: float
    gf_dma_fcf_weight: float
    gf_dma_revision_adjustment: float
    gf_dma_relative_strength_adjustment: float
    gf_dma_valuation_expansion_penalty: float
    required_monitoring_indicators: tuple[str, ...]
    view_change_triggers: tuple[str, ...]


AI_ACCELERATOR_LEADER = CompanyArchetypeProfile(
    key="ai_accelerator_leader",
    display_name="AI accelerator leader",
    investment_view=(
        "This archetype should be evaluated through AI accelerator demand, "
        "gross-margin durability, hyperscaler capex signals, supply constraints, "
        "and valuation compression risk."
    ),
    bayesian_revenue_weight=1.10,
    bayesian_margin_weight=1.20,
    bayesian_fcf_weight=1.10,
    bayesian_backlog_weight=1.05,
    bayesian_hyperscaler_weight=1.25,
    bayesian_ai_exposure_weight=1.20,
    gf_dma_revenue_weight=1.00,
    gf_dma_eps_weight=1.05,
    gf_dma_fcf_weight=1.05,
    gf_dma_revision_adjustment=0.00,
    gf_dma_relative_strength_adjustment=0.02,
    gf_dma_valuation_expansion_penalty=0.04,
    required_monitoring_indicators=(
        "AI accelerator demand and data-center revenue growth",
        "Gross margin durability",
        "Hyperscaler capex plans",
        "HBM and advanced packaging availability",
        "Valuation multiple compression risk",
    ),
    view_change_triggers=(
        "AI accelerator demand decelerates materially.",
        "Gross margins compress faster than scenario assumptions.",
        "Hyperscaler capex plans weaken or shift away from the platform.",
        "Valuation multiple compression overwhelms earnings growth.",
    ),
)


SEMICAP_EQUIPMENT_BOTTLENECK = CompanyArchetypeProfile(
    key="semicap_equipment_bottleneck",
    display_name="Semiconductor equipment bottleneck",
    investment_view=(
        "This archetype should be evaluated through backlog quality, lithography "
        "monopoly-like positioning, China and export-control risk, and the "
        "semiconductor capital-equipment cycle."
    ),
    bayesian_revenue_weight=0.85,
    bayesian_margin_weight=1.10,
    bayesian_fcf_weight=0.95,
    bayesian_backlog_weight=1.35,
    bayesian_hyperscaler_weight=0.45,
    bayesian_ai_exposure_weight=0.60,
    gf_dma_revenue_weight=0.85,
    gf_dma_eps_weight=0.95,
    gf_dma_fcf_weight=0.90,
    gf_dma_revision_adjustment=0.00,
    gf_dma_relative_strength_adjustment=-0.01,
    gf_dma_valuation_expansion_penalty=0.08,
    required_monitoring_indicators=(
        "Backlog and order-book durability",
        "EUV and High-NA adoption milestones",
        "China and export-control developments",
        "Foundry and memory capex cycle",
        "Customer fab utilization",
    ),
    view_change_triggers=(
        "Backlog weakens or cancellations rise.",
        "China/export-control restrictions materially change shipment assumptions.",
        "Foundry or memory capex plans are cut.",
        "High-NA adoption milestones slip.",
    ),
)


SPECULATIVE_AI_INFRASTRUCTURE = CompanyArchetypeProfile(
    key="speculative_ai_infrastructure",
    display_name="Speculative AI infrastructure",
    investment_view=(
        "This archetype should be evaluated through revenue growth, AI cloud "
        "demand, utilization, execution risk, financing runway, dilution risk, "
        "and speculative valuation support."
    ),
    bayesian_revenue_weight=1.20,
    bayesian_margin_weight=0.55,
    bayesian_fcf_weight=0.35,
    bayesian_backlog_weight=1.25,
    bayesian_hyperscaler_weight=1.15,
    bayesian_ai_exposure_weight=1.10,
    gf_dma_revenue_weight=0.95,
    gf_dma_eps_weight=0.45,
    gf_dma_fcf_weight=0.30,
    gf_dma_revision_adjustment=-0.08,
    gf_dma_relative_strength_adjustment=-0.05,
    gf_dma_valuation_expansion_penalty=0.25,
    required_monitoring_indicators=(
        "Revenue growth and AI cloud utilization",
        "Signed customer backlog and contract duration",
        "Financing runway and dilution risk",
        "Gross margin progression",
        "Data-center power and GPU availability",
        "Speculative valuation support",
    ),
    view_change_triggers=(
        "Utilization fails to scale with capacity additions.",
        "Funding runway worsens or dilution accelerates.",
        "AI cloud pricing weakens materially.",
        "Gross margin progression stalls.",
        "Customer concentration rises without longer contract duration.",
    ),
)


DEFAULT_ARCHETYPE = AI_ACCELERATOR_LEADER


ARCHETYPE_BY_TICKER = {
    "NVDA": AI_ACCELERATOR_LEADER,
    "AMD": AI_ACCELERATOR_LEADER,
    "ASML": SEMICAP_EQUIPMENT_BOTTLENECK,
    "NBIS": SPECULATIVE_AI_INFRASTRUCTURE,
}


def archetype_for_company(company: CompanyMockData) -> CompanyArchetypeProfile:
    """Return the mock archetype profile for a company."""

    return ARCHETYPE_BY_TICKER.get(company.ticker, DEFAULT_ARCHETYPE)
