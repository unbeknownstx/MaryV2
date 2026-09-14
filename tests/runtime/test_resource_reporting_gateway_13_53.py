from mary.distributed.resource_probe import GPUObservation, LiveResourceObservation
from mary.runtime.resource_reporting_gateway import ResourceReportingGateway


class _Gateway:
    def __init__(self):
        self.device_id = "node-a"
        self.calls = []

    def complete_capability_task(self, task_id, *, status, result=None, error=""):
        payload = {
            "task_id": task_id,
            "status": status,
            "result": dict(result or {}),
            "error": error,
        }
        self.calls.append(payload)
        return {"ok": True, **payload}


def _observation():
    return LiveResourceObservation(
        platform="windows",
        ram_total_gib=32.0,
        ram_free_gib=12.0,
        gpus=(
            GPUObservation(
                label="test-gpu",
                total_gib=16.0,
                free_gib=4.0,
                backend="cuda",
                source="nvidia_smi",
            ),
        ),
        apple_unified_memory=False,
    )


def test_success_attaches_raw_allowlisted_resource_payload_and_caches_probe():
    gateway = _Gateway()
    calls = {"count": 0}

    def observer():
        calls["count"] += 1
        return _observation()

    wrapped = ResourceReportingGateway(gateway, sample_seconds=30.0, observer=observer)
    wrapped.complete_capability_task("capability_task_a", status="completed", result={"content": "one"})
    wrapped.complete_capability_task("capability_task_b", status="completed", result={"content": "two"})

    assert calls["count"] == 1
    resource = gateway.calls[0]["result"]["_resource"]
    assert resource == {
        "ram_total_gib": 32.0,
        "ram_free_gib": 12.0,
        "vram_total_gib": 16.0,
        "vram_free_gib": 4.0,
        "apple_unified_memory": False,
        "source": "mixed",
    }
    assert "memory_fraction" not in resource
    assert "accelerator_fraction" not in resource
    assert gateway.calls[1]["result"]["_resource"] == resource


def test_rejected_and_failed_completions_never_probe_or_attach_resources():
    gateway = _Gateway()
    calls = {"count": 0}

    def observer():
        calls["count"] += 1
        return _observation()

    wrapped = ResourceReportingGateway(gateway, observer=observer)
    wrapped.complete_capability_task("capability_task_a", status="rejected", error="permission denied")
    wrapped.complete_capability_task("capability_task_b", status="failed", error="runtime failed")

    assert calls["count"] == 0
    assert gateway.calls[0]["result"] == {}
    assert gateway.calls[1]["result"] == {}


def test_full_eight_field_business_result_is_preserved_without_resource_injection():
    gateway = _Gateway()
    wrapped = ResourceReportingGateway(gateway, observer=_observation)
    result = {f"field_{index}": index for index in range(8)}

    wrapped.complete_capability_task("capability_task_a", status="completed", result=result)

    assert gateway.calls[0]["result"] == result
    assert "_resource" not in gateway.calls[0]["result"]


def test_probe_failure_is_soft_and_does_not_change_successful_completion():
    gateway = _Gateway()

    def observer():
        raise RuntimeError("probe unavailable")

    wrapped = ResourceReportingGateway(gateway, observer=observer)
    response = wrapped.complete_capability_task(
        "capability_task_a",
        status="completed",
        result={"content": "ok"},
    )

    assert response["ok"] is True
    assert gateway.calls[0]["status"] == "completed"
    assert gateway.calls[0]["result"] == {"content": "ok"}
