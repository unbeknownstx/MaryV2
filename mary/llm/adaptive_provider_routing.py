"""Bounded adaptive provider scoring for MaryV2 13.63.

The scorer is advisory only. Privacy, permission, cost, capability, and explicit
route eligibility MUST be applied before candidates reach this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

VERSION = "13.63"


@dataclass(frozen=True)
class ProviderEvidence:
    provider: str
    reliability: float | None = None
    latency_ms: float | None = None
    quota_remaining: float | None = None
    capability_fit: float | None = None
    samples: int = 0


@dataclass(frozen=True)
class RoutingWeights:
    reliability: float = 0.40
    latency: float = 0.20
    quota: float = 0.25
    capability: float = 0.15


def _unit(value: float | None, default: float = 0.5) -> float:
    if value is None:
        return default
    value = float(value)
    if not math.isfinite(value):
        return default
    return max(0.0, min(1.0, value))


def score_provider(evidence: ProviderEvidence, *, task_type: str = "general", weights: RoutingWeights | None = None) -> float:
    """Score already-eligible providers without examining request content."""
    w = weights or RoutingWeights()
    reliability = _unit(evidence.reliability)
    quota = _unit(evidence.quota_remaining)
    capability = _unit(evidence.capability_fit)
    latency = 0.5 if evidence.latency_ms is None else 1.0 / (1.0 + max(0.0, float(evidence.latency_ms)) / 1500.0)
    task = str(task_type).strip().lower()
    # Explicit task labels only; never infer task type from private prompt text.
    capability_weight = w.capability
    latency_weight = w.latency
    if task in {"code", "reasoning", "analysis"}:
        capability_weight += 0.10
        latency_weight = max(0.0, latency_weight - 0.10)
    elif task in {"chat", "conversation", "social_instant"}:
        latency_weight += 0.10
        capability_weight = max(0.0, capability_weight - 0.10)
    return (w.reliability * reliability) + (latency_weight * latency) + (w.quota * quota) + (capability_weight * capability)


def choose_provider(candidates: list[ProviderEvidence], *, task_type: str = "general", current_provider: str | None = None, switch_margin: float = 0.08, explore: bool = False) -> str | None:
    """Choose with hysteresis; optional exploration only targets unmeasured peers.

    Exploration is deterministic here: the first unmeasured eligible candidate
    may be selected. Callers decide when an exploration turn is allowed.
    """
    if not candidates:
        return None
    if explore:
        for item in candidates:
            if item.samples <= 0:
                return item.provider
    ranked = sorted(candidates, key=lambda item: (-score_provider(item, task_type=task_type), item.provider))
    best = ranked[0]
    if current_provider:
        current = next((item for item in candidates if item.provider == current_provider), None)
        if current is not None:
            if score_provider(best, task_type=task_type) < score_provider(current, task_type=task_type) + max(0.0, float(switch_margin)):
                return current.provider
    return best.provider
