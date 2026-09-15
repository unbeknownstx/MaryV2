from mary.distributed.model_residency import ResidentModel, plan_model_residency
from mary.distributed.resource_broker import ResourceSnapshot, WorkloadFootprint


def test_unknown_free_vram_never_speculatively_evicts():
    snapshot = ResourceSnapshot(node_id="pc", vram_total_gb=12.0, vram_free_gb=None)
    plan = plan_model_residency(
        snapshot,
        [ResidentModel("qwen", 4.0, last_used_seconds_ago=5000)],
        incoming=WorkloadFootprint("image", vram_gb=8.0),
    )
    assert plan.pressure == "unknown"
    assert plan.decisions[0].action == "keep"
    assert plan.enough_after_plan is None


def test_realtime_conversation_model_is_protected_under_pressure():
    snapshot = ResourceSnapshot(node_id="pc", vram_total_gb=12.0, vram_free_gb=2.0)
    plan = plan_model_residency(
        snapshot,
        [
            ResidentModel("conversation", 4.0, role="conversation", last_used_seconds_ago=1200),
            ResidentModel("old-vision", 5.0, role="vision", last_used_seconds_ago=5000),
        ],
        incoming=WorkloadFootprint("image", vram_gb=6.0),
    )
    decisions = {item.model_id: item for item in plan.decisions}
    assert decisions["conversation"].action == "keep"
    assert decisions["old-vision"].action == "release_candidate"


def test_stale_lower_priority_model_can_yield_to_incoming_workload():
    snapshot = ResourceSnapshot(node_id="gpu", vram_total_gb=24.0, vram_free_gb=5.0)
    plan = plan_model_residency(
        snapshot,
        [ResidentModel("batch-model", 6.0, role="batch", last_used_seconds_ago=3600)],
        incoming=WorkloadFootprint("video", vram_gb=10.0),
        reserve_vram_gb=1.0,
    )
    assert plan.pressure == "constrained"
    assert plan.decisions[0].action == "release_candidate"
    assert plan.decisions[0].estimated_reclaimed_vram_gb == 6.0
    assert plan.enough_after_plan is True


def test_pinned_model_is_never_selected_by_planner():
    snapshot = ResourceSnapshot(node_id="gpu", vram_total_gb=12.0, vram_free_gb=1.0)
    plan = plan_model_residency(
        snapshot,
        [ResidentModel("pinned", 8.0, pinned=True, last_used_seconds_ago=99999)],
        incoming=WorkloadFootprint("video", vram_gb=6.0),
    )
    assert plan.decisions[0].action == "keep"
    assert plan.decisions[0].reason == "pinned"
    assert plan.enough_after_plan is False


def test_recent_expensive_model_can_be_kept_when_pressure_is_not_critical():
    snapshot = ResourceSnapshot(node_id="gpu", vram_total_gb=24.0, vram_free_gb=5.0)
    plan = plan_model_residency(
        snapshot,
        [ResidentModel("costly", 8.0, last_used_seconds_ago=60, reload_cost_seconds=9.0)],
        incoming=WorkloadFootprint("job", vram_gb=6.0),
        reserve_vram_gb=1.0,
    )
    assert plan.pressure == "constrained"
    assert plan.decisions[0].action == "keep"
    assert plan.enough_after_plan is False


def test_plan_is_advisory_only():
    snapshot = ResourceSnapshot(node_id="gpu", vram_total_gb=12.0, vram_free_gb=2.0)
    plan = plan_model_residency(
        snapshot,
        [ResidentModel("old", 4.0, last_used_seconds_ago=5000)],
        incoming=WorkloadFootprint("job", vram_gb=5.0),
    )
    assert plan.to_dict()["authority"] == "planning_only"
