from mary.distributed.resource_broker import ResourceSnapshot, WorkloadFootprint, plan_resource_handoff


def test_resource_broker_uses_free_vram_before_evicting_warm_model():
    plan = plan_resource_handoff(
        ResourceSnapshot(node_id="gpu", vram_total_gb=24, vram_free_gb=12, loaded_models=("chat",)),
        WorkloadFootprint(name="image", vram_gb=10),
    )
    assert plan.status == "fits"
    assert plan.unload_warm_models is False


def test_resource_broker_plans_state_preserving_handoff_when_workload_only_fits_after_release():
    plan = plan_resource_handoff(
        ResourceSnapshot(node_id="gpu", vram_total_gb=16, vram_free_gb=4, loaded_models=("chat",)),
        WorkloadFootprint(name="video", vram_gb=12, prefers_exclusive_accelerator=True),
    )
    assert plan.status == "handoff"
    assert plan.unload_warm_models is True
    assert plan.preserve_warm_state is True
    assert plan.restore_after is True
    assert plan.serialize_key == "accelerator:shared"


def test_resource_broker_does_not_evict_on_unknown_measurement():
    plan = plan_resource_handoff(
        ResourceSnapshot(node_id="gpu", loaded_models=("chat",)),
        WorkloadFootprint(name="video", vram_gb=12),
    )
    assert plan.status == "unknown"
    assert plan.unload_warm_models is False


def test_resource_broker_protects_realtime_resident_node_from_background_gpu_work():
    plan = plan_resource_handoff(
        ResourceSnapshot(node_id="stream", vram_total_gb=24, vram_free_gb=10, active_realtime=True),
        WorkloadFootprint(name="background-render", vram_gb=8, realtime=False),
    )
    assert plan.status == "prefer_other_node"
