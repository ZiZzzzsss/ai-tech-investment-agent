"""Provider status models for diagnostics and report rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderStatus:
    """One provider readiness row for source-status tables."""

    provider: str
    configured: str
    used: str
    availability: str
    reason: str
    last_successful_retrieval: str


__all__ = ["ProviderStatus"]
