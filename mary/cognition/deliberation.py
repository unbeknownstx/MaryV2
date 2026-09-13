"""Adaptive, content-free deliberation policy for MaryV2.

The governor selects how much *process* a turn deserves without exposing or
persisting private chain-of-thought. It is a policy layer only: model/provider
authorization, paid use, tools, memory writes and identity remain owned by their
existing Mary systems.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


@dataclass(frozen=True)
class DeliberationPlan:
    strategy: str
    max_passes: int
    max_branches: int
    verifier_required: bool
    confidence_floor: float
    latency_budget_ms: int
    external_verifier_allowed: bool
    workspace_fields: tuple[str, ...] = (
        "facts",
        "constraints",
        "unknowns",
        "candidate_actions",
        "confidence",
    )
    persistence: str = "ephemeral_structural_state_only"
    expose_private_reasoning: bool = False
    authority: str = "cognition_policy_only"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["workspace_fields"] = list(self.workspace_fields)
        return payload


class DeliberationGovernor:
    """Choose bounded test-time compute from an existing cognitive plan."""

    VERSION = "13.29"

    def __init__(
        self,
        *,
        max_passes: int = 4,
        max_branches: int = 3,
        default_confidence_floor: float = 0.78,
    ) -> None:
        self.max_passes = max(1, min(8, int(max_passes)))
        self.max_branches = max(1, min(4, int(max_branches)))
        self.default_confidence_floor = _clamp(
            default_confidence_floor, 0.50, 0.99
        )

    def plan(
        self,
        cognitive_plan: dict[str, Any] | None,
        *,
        uncertainty: float | None = None,
        verifier_available: bool = True,
        external_verifier_authorized: bool = False,
        realtime: bool = False,
    ) -> DeliberationPlan:
        plan = dict(cognitive_plan or {})
        mode = str(plan.get("cognitive_mode") or "balanced").strip().lower()
        depth = str(plan.get("reasoning_depth") or "moderate").strip().lower()
        latency = str(plan.get("latency_priority") or "responsive").strip().lower()

        if uncertainty is None:
            uncertainty = {
                "light": 0.18,
                "moderate": 0.34,
                "deep": 0.52,
            }.get(depth, 0.34)
        uncertainty = _clamp(uncertainty, 0.0, 1.0)

        if mode in {"direct", "relational"} and depth != "deep":
            strategy = "single_pass"
            passes = 1
            branches = 1
            verifier_required = False
        elif mode == "deliberate" or depth == "deep":
            if verifier_available and uncertainty >= 0.45:
                strategy = "branch_verify"
                passes = 3
                branches = 2
                verifier_required = True
            elif verifier_available:
                strategy = "verify_once"
                passes = 2
                branches = 1
                verifier_required = True
            else:
                strategy = "single_pass"
                passes = 1
                branches = 1
                verifier_required = False
        else:
            if verifier_available and uncertainty >= 0.50:
                strategy = "verify_once"
                passes = 2
                branches = 1
                verifier_required = True
            else:
                strategy = "single_pass"
                passes = 1
                branches = 1
                verifier_required = False

        passes = min(self.max_passes, passes)
        branches = min(self.max_branches, branches)

        budget = {
            "fast": 1800,
            "responsive": 4000,
            "quality_first": 12000,
        }.get(latency, 5000)
        if realtime:
            budget = min(budget, 3200)
            if strategy == "branch_verify":
                strategy = "verify_once"
                branches = 1
                passes = min(passes, 2)

        confidence_floor = self.default_confidence_floor
        if mode == "deliberate":
            confidence_floor = max(confidence_floor, 0.84)
        elif mode == "direct":
            confidence_floor = min(confidence_floor, 0.74)

        return DeliberationPlan(
            strategy=strategy,
            max_passes=passes,
            max_branches=branches,
            verifier_required=verifier_required,
            confidence_floor=round(confidence_floor, 3),
            latency_budget_ms=budget,
            external_verifier_allowed=bool(external_verifier_authorized),
        )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "max_passes": self.max_passes,
            "max_branches": self.max_branches,
            "default_confidence_floor": self.default_confidence_floor,
            "private_reasoning_persistence": False,
            "private_reasoning_exposure": False,
            "automatic_training": False,
            "authority": "cognition_policy_only",
        }
