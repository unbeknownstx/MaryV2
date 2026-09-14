"""Advisory model-residency planning for finite Mary compute nodes.

Residency planning decides which already-loaded replaceable models are worth
keeping warm under measured resource pressure. It never unloads a model itself.
Actual lifecycle actions remain node-owned, permission-gated capabilities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .resource_broker import ResourceSnapshot, WorkloadFootprint

VERSION = "13.45"


@dataclass(frozen=True)
class ResidentModel:
    model_id: str
    vram_gb: float
    role: str = "general"
    last_used_seconds_ago: float = 0.0
    pinned: bool = False
    realtime: bool = False
    reload_cost_seconds: float = 0.0

    def __post_init__(self) -> None:
        model_id = str(self.model_id or "").strip()[:240]
        if not model_id:
            raise ValueError("resident model_id is required")
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "vram_gb", max(0.0, float(self.vram_gb)))
        object.__setattr__(self, "role", str(self.role or "general").strip().lower()[:80])
        object.__setattr__(self, "last_used_seconds_ago", max(0.0, float(self.last_used_seconds_ago)))
        object.__setattr__(self, "reload_cost_seconds", max(0.0, float(self.reload_cost_seconds)))


@dataclass(frozen=True)
class ResidencyDecision:
    model_id: str
    action: str
    reason: str
    estimated_reclaimed_vram_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResidencyPlan:
    node_id: str
    pressure: str
    incoming_vram_gb: float
    measured_free_vram_gb: float | None
    decisions: tuple[ResidencyDecision, ...]
    enough_after_plan: bool | None
    version: str = VERSION
    authority: str = "planning_only"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decisions"] = [item.to_dict() for item in self.decisions]
        return payload


def _eviction_score(model: ResidentModel) -> tuple[int, int, float, float, str]:
    """Lower tuple means safer/more useful eviction candidate."""
    return (
        1 if model.pinned else 0,
        1 if model.realtime else 0,
        -model.last_used_seconds_ago,
        -model.vram_gb,
        model.model_id,
    )


def plan_model_residency(
    snapshot: ResourceSnapshot,
    resident_models: Sequence[ResidentModel],
    *,
    incoming: WorkloadFootprint | None = None,
    reserve_vram_gb: float = 0.75,
    stale_after_seconds: float = 900.0,
) -> ResidencyPlan:
    """Plan warm-model retention/eviction from measured pressure.

    Unknown free VRAM yields no speculative eviction. Pinned or realtime models
    are retained unless a future explicit policy chooses otherwise.
    """
    reserve = max(0.0, float(reserve_vram_gb))
    incoming_vram = max(0.0, float(getattr(incoming, "vram_gb", 0.0) or 0.0))
    free = snapshot.vram_free_gb
    total = snapshot.vram_total_gb
    models = list(resident_models)

    if free is None:
        return ResidencyPlan(
            node_id=snapshot.node_id,
            pressure="unknown",
            incoming_vram_gb=incoming_vram,
            measured_free_vram_gb=None,
            decisions=tuple(
                ResidencyDecision(item.model_id, "keep", "free_vram_unknown_no_speculative_eviction")
                for item in models
            ),
            enough_after_plan=None,
        )

    target_free = incoming_vram + reserve
    deficit = max(0.0, target_free - max(0.0, float(free)))
    if total is not None and incoming_vram > max(0.0, float(total)):
        pressure = "does_not_fit_total_vram"
    elif deficit <= 0.0:
        pressure = "comfortable"
    elif free <= reserve:
        pressure = "critical"
    else:
        pressure = "constrained"

    decisions: list[ResidencyDecision] = []
    reclaimed = 0.0
    candidates: list[ResidentModel] = []
    protected: set[str] = set()

    for model in models:
        if model.pinned:
            protected.add(model.model_id)
            decisions.append(ResidencyDecision(model.model_id, "keep", "pinned"))
        elif model.realtime or model.role in {"conversation", "fast", "stt", "tts", "vad"}:
            protected.add(model.model_id)
            decisions.append(ResidencyDecision(model.model_id, "keep", "realtime_or_interactive_lane"))
        else:
            candidates.append(model)

    for model in sorted(candidates, key=_eviction_score):
        if reclaimed >= deficit:
            reason = (
                "keep_warm_reload_cost"
                if model.reload_cost_seconds >= 3.0
                else "resource_headroom_sufficient"
            )
            decisions.append(ResidencyDecision(model.model_id, "keep", reason))
            continue
        stale = model.last_used_seconds_ago >= max(0.0, float(stale_after_seconds))
        if not stale and model.reload_cost_seconds >= 5.0 and pressure != "critical":
            decisions.append(ResidencyDecision(model.model_id, "keep", "recent_and_expensive_to_reload"))
            continue
        reclaimed += model.vram_gb
        decisions.append(
            ResidencyDecision(
                model.model_id,
                "release_candidate",
                "stale_or_lower_priority_under_measured_pressure",
                estimated_reclaimed_vram_gb=round(model.vram_gb, 3),
            )
        )

    enough = (max(0.0, float(free)) + reclaimed) >= target_free
    return ResidencyPlan(
        node_id=snapshot.node_id,
        pressure=pressure,
        incoming_vram_gb=round(incoming_vram, 3),
        measured_free_vram_gb=round(float(free), 3),
        decisions=tuple(decisions),
        enough_after_plan=enough,
    )
