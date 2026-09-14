from threading import Event

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
    ready = Event()

    def observer():
        calls["count"] += 1
        ready.set()
        return _observation()

    wrapped = ResourceReportingGateway(gateway, sample_seconds=30.0, observer=observer)
    assert ready.wait(1.0)
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


def test_rejected_and_failed_completions_do_not_trigger_resource_refresh():
    gateway = _Gateway()
    calls = {"count": 0}
    ready = Event()

    def observer():
        calls["count"] += 1
        ready.set()
        return _observation()

    wrapped = ResourceReportingGateway(gateway, observer=observer)
    assert ready.wait(1.0)
    wrapped.complete_capability_task("capability_task_a", status="rejected", error="permission denied")
    wrapped.complete_capability_task("capability_task_b", status="failed", error="runtime failed")

    assert calls["count"] == 1
    assert gateway.calls[0]["result"] == {}
    assert gateway.calls[1]["result"] == {}


def test_full_eight_field_business_result_is_preserved_without_resource_injection():
    gateway = _Gateway()
    ready = Event()

    def observer():
        ready.set()
        return _observation()

    wrapped = ResourceReportingGateway(gateway, observer=observer)
    assert ready.wait(1.0)
    result = {f"field_{index}": index for index in range(8)}

    wrapped.complete_capability_task("capability_task_a", status="completed", result=result)

    assert gateway.calls[0]["result"] == result
    assert "_resource" not in gateway.calls[0]["result"]


def test_probe_failure_is_soft_and_does_not_change_successful_completion():
    gateway = _Gateway()
    finished = Event()

    def observer():
        finished.set()
        raise RuntimeError("probe unavailable")

    wrapped = ResourceReportingGateway(gateway, observer=observer)
    assert finished.wait(1.0)
    response = wrapped.complete_capability_task(
        "capability_task_a",
        status="completed",
        result={"content": "ok"},
    )

    assert response["ok"] is True
    assert gateway.calls[0]["status"] == "completed"
    assert gateway.calls[0]["result"] == {"content": "ok"}


def test_completion_uses_no_resource_envelope_while_background_probe_is_busy():
    gateway = _Gateway()
    entered = Event()
    release = Event()

    def observer():
        entered.set()
        release.wait(1.0)
        return _observation()

    wrapped = ResourceReportingGateway(gateway, observer=observer)
    assert entered.wait(1.0)
    response = wrapped.complete_capability_task(
        "capability_task_a",
        status="completed",
        result={"content": "fast"},
    )
    release.set()

    assert response["ok"] is True
    assert gateway.calls[0]["result"] == {"content": "fast"}
