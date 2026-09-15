"""Advisory RAM/VRAM hand-off planning for Mary's heterogeneous compute fabric.

The broker never unloads a model, launches a process, or grants device authority.
It only turns measured resource facts into an explicit plan that an already-
authorized node runtime may choose to implement.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


VERSION = "13.37"


@dataclass(frozen=True)
class ResourceSnapshot:
    node_id: str
    ram_total_gb: float | None = None
    ram_free_gb: float | None = None
    vram_total_gb: float | None = None
    vram_free_gb: float | None = None
    loaded_models: tuple[str, ...] = ()
    active_realtime: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkloadFootprint:
    name: str
    ram_gb: float | None = None
    vram_gb: float | None = None
    prefers_exclusive_accelerator: bool = False
    realtime: bool = False


@dataclass(frozen=True)
class ResourceHandoffPlan:
    node_id: str
    status: str
    unload_warm_models: bool
    preserve_warm_state: bool
    restore_after: bool
    serialize_key: str | None
    reason: str
    authority: str = "planning_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nonnegative(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def plan_resource_handoff(
    snapshot: ResourceSnapshot,
    workload: WorkloadFootprint,
    *,
    warm_model_vram_gb: float | None = None,
    policy: str = "auto",
) -> ResourceHandoffPlan:
    """Plan whether warm inference state should yield to another GPU workload.

    ``auto`` refuses to evict on unknown measurements. ``always`` explicitly
    opts into a hand-off when a warm model is resident. ``never`` preserves the
    current resident state and lets the authorized runtime surface a real OOM.
    """

    mode = str(policy or "auto").strip().lower()
    if mode not in {"auto", "always", "never"}:
        raise ValueError("resource handoff policy must be auto, always, or never")

    warm = _nonnegative(warm_model_vram_gb)
    needed = _nonnegative(workload.vram_gb)
    total = _nonnegative(snapshot.vram_total_gb)
    free = _nonnegative(snapshot.vram_free_gb)
    has_warm = bool(snapshot.loaded_models) or bool(warm and warm > 0)
    accelerator_task = needed is not None and needed > 0
    serialize_key = "accelerator:shared" if accelerator_task or workload.prefers_exclusive_accelerator else None

    if mode == "never":
        return ResourceHandoffPlan(
            node_id=snapshot.node_id,
            status="attempt_in_place",
            unload_warm_models=False,
            preserve_warm_state=False,
            restore_after=False,
            serialize_key=serialize_key,
            reason="policy_never",
        )

    if snapshot.active_realtime and not workload.realtime:
        return ResourceHandoffPlan(
            node_id=snapshot.node_id,
            status="prefer_other_node",
            unload_warm_models=False,
            preserve_warm_state=False,
            restore_after=False,
            serialize_key=serialize_key,
            reason="protect_realtime_residency",
        )

    if mode == "always" and has_warm and accelerator_task:
        return ResourceHandoffPlan(
            node_id=snapshot.node_id,
            status="handoff",
            unload_warm_models=True,
            preserve_warm_state=True,
            restore_after=True,
            serialize_key=serialize_key,
            reason="policy_always_with_resident_model",
        )

    if not accelerator_task:
        return ResourceHandoffPlan(
            node_id=snapshot.node_id,
            status="no_handoff_needed",
            unload_warm_models=False,
            preserve_warm_state=False,
            restore_after=False,
            serialize_key=serialize_key,
            reason="workload_has_no_vram_requirement",
        )

    # Prefer the live free-VRAM observation when available. It directly answers
    # whether the incoming workload fits without speculating about model size.
    if free is not None:
        if needed <= free:
            return ResourceHandoffPlan(
                node_id=snapshot.node_id,
                status="fits",
                unload_warm_models=False,
                preserve_warm_state=False,
                restore_after=False,
                serialize_key=serialize_key,
                reason="measured_free_vram_is_sufficient",
            )
        if has_warm and total is not None and needed <= total:
            return ResourceHandoffPlan(
                node_id=snapshot.node_id,
                status="handoff",
                unload_warm_models=True,
                preserve_warm_state=True,
                restore_after=True,
                serialize_key=serialize_key,
                reason="workload_fits_only_after_releasing_resident_vram",
            )
        if total is not None and needed > total:
            return ResourceHandoffPlan(
                node_id=snapshot.node_id,
                status="infeasible",
                unload_warm_models=False,
                preserve_warm_state=False,
                restore_after=False,
                serialize_key=serialize_key,
                reason="workload_exceeds_total_vram",
            )

    # Fallback math when free VRAM is unavailable but the resident footprint is measured.
    if total is not None and warm is not None:
        if warm + needed > total and needed <= total and has_warm:
            return ResourceHandoffPlan(
                node_id=snapshot.node_id,
                status="handoff",
                unload_warm_models=True,
                preserve_warm_state=True,
                restore_after=True,
                serialize_key=serialize_key,
                reason="resident_plus_workload_exceeds_total_vram",
            )
        if warm + needed <= total:
            return ResourceHandoffPlan(
                node_id=snapshot.node_id,
                status="fits",
                unload_warm_models=False,
                preserve_warm_state=False,
                restore_after=False,
                serialize_key=serialize_key,
                reason="measured_resident_plus_workload_fits",
            )

    return ResourceHandoffPlan(
        node_id=snapshot.node_id,
        status="unknown",
        unload_warm_models=False,
        preserve_warm_state=False,
        restore_after=False,
        serialize_key=serialize_key,
        reason="insufficient_resource_measurement_do_not_evict_on_guess",
    )
