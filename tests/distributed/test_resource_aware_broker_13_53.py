from time import monotonic

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.tasks import DeviceTaskBroker


def _node(node_id: str, latency_ms: float) -> NodeDescriptor:
    return NodeDescriptor(
        node_id=node_id,
        role="capability_node",
        host_type="capability_node",
        platform="test",
        capabilities={
            "llm.ollama": CapabilityDescriptor(
                "llm.ollama",
                private=True,
                local=True,
                cost="local",
                metadata={
                    "benchmark_latency_ms": latency_ms,
                    "benchmark_success_rate": 1.0,
                },
            )
        },
    )


def _registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(_node("a-idle", 900.0))
    registry.register(_node("z-fast", 300.0))
    return registry


def _args():
    return {
        "messages": [{"role": "user", "content": "hello"}],
        "role": "utility",
        "temperature": 0.2,
        "max_tokens": 64,
    }


def test_fresh_accelerator_pressure_can_move_work_off_static_fast_node():
    registry = _registry()
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("z-fast", {
        "ram_total_gib": 32,
        "ram_free_gib": 16,
        "vram_total_gib": 8,
        "vram_free_gib": 0.4,
        "source": "nvidia_smi",
    })

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="background utility",
        args=_args(),
        requester_device_id="creator",
    )
    assert task.selected_node_id == "a-idle"
    assert broker.compute_status()["live_load"]["z-fast"]["accelerator_fraction"] == 0.95


def test_stale_resource_report_stops_influencing_routing():
    registry = _registry()
    broker = DeviceTaskBroker(resource_ttl_seconds=10.0)
    broker.update_resource_telemetry("z-fast", {
        "vram_total_gib": 8,
        "vram_free_gib": 0.4,
        "source": "nvidia_smi",
    })
    measured_at, report = broker._resources["z-fast"]
    broker._resources["z-fast"] = (monotonic() - 11.0, report)

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="background utility",
        args=_args(),
        requester_device_id="creator",
    )
    assert task.selected_node_id == "z-fast"
    assert broker.compute_status()["resource_reports"] == 0


def test_completion_resource_payload_is_stripped_before_result_storage():
    registry = _registry()
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )
    broker.poll(task.selected_node_id)
    completed = broker.complete(
        node_id=task.selected_node_id,
        task_id=task.task_id,
        status="completed",
        result={
            "content": "answer",
            "model": "qwen",
            "_resource": {
                "ram_total_gib": 32,
                "ram_free_gib": 8,
                "vram_total_gib": 8,
                "vram_free_gib": 2,
                "source": "nvidia_smi",
            },
        },
    )
    assert "_resource" not in completed.result
    assert "_resource" not in str(broker.snapshot())
    assert broker.compute_status()["resource_reports"] == 1


def test_malformed_resource_payload_does_not_break_task_completion():
    registry = _registry()
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )
    broker.poll(task.selected_node_id)
    completed = broker.complete(
        node_id=task.selected_node_id,
        task_id=task.task_id,
        status="completed",
        result={
            "content": "answer",
            "model": "qwen",
            "_resource": {"process_list": ["should-not-be-accepted"]},
        },
    )
    assert completed.status == "completed"
    assert completed.result["content"] == "answer"
    assert broker.compute_status()["resource_reports"] == 0
    assert broker.compute_status()["resource_rejections"] == 1
    assert "should-not-be-accepted" not in str(broker.compute_status())


def test_completion_report_can_change_followup_routing():
    registry = _registry()
    broker = DeviceTaskBroker()
    first = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="first",
        args=_args(),
        requester_device_id="creator",
    )
    assert first.selected_node_id == "z-fast"
    broker.poll("z-fast")
    broker.complete(
        node_id="z-fast",
        task_id=first.task_id,
        status="completed",
        result={
            "content": "answer",
            "model": "qwen",
            "_resource": {
                "ram_total_gib": 32,
                "ram_free_gib": 4,
                "vram_total_gib": 8,
                "vram_free_gib": 0.4,
                "source": "nvidia_smi",
            },
        },
    )

    second = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="second",
        args=_args(),
        requester_device_id="creator",
    )
    assert second.selected_node_id == "a-idle"
