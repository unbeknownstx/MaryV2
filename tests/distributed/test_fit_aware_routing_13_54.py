from time import monotonic

import pytest

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.compute_fabric import HomeComputeScheduler, NodeLoad, WorkloadRequest
from mary.distributed.resource_requirements import apply_explicit_resource_requirements
from mary.distributed.resource_telemetry import sanitize_resource_telemetry
from mary.distributed.tasks import DeviceTaskBroker
from mary.runtime.resource_reporting_gateway import ResourceReportingGateway


def _node(node_id: str, latency_ms: float, *, required_gib: float | None = None) -> NodeDescriptor:
    metadata = {
        "benchmark_latency_ms": latency_ms,
        "benchmark_success_rate": 1.0,
    }
    if required_gib is not None:
        metadata["resource_accelerator_gib_utility"] = required_gib
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
                metadata=metadata,
            )
        },
    )


def _registry(*, with_requirements: bool = True) -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(_node("a-roomy", 900.0, required_gib=2.0 if with_requirements else None))
    registry.register(_node("z-fast", 300.0, required_gib=8.0 if with_requirements else None))
    return registry


def _utility_args() -> dict:
    return {
        "messages": [{"role": "user", "content": "bounded private work"}],
        "role": "utility",
        "temperature": 0.2,
        "max_tokens": 64,
    }


def _report(total: float, free: float, *, unified: bool = False) -> dict:
    if unified:
        return {
            "ram_total_gib": total,
            "ram_free_gib": free,
            "vram_total_gib": None,
            "vram_free_gib": None,
            "apple_unified_memory": True,
            "source": "apple_unified_memory",
        }
    return {
        "ram_total_gib": 32.0,
        "ram_free_gib": 24.0,
        "vram_total_gib": total,
        "vram_free_gib": free,
        "apple_unified_memory": False,
        "source": "nvidia_smi",
    }


def test_broker_routes_away_from_explicitly_measured_no_fit_node():
    registry = _registry()
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("z-fast", _report(4.0, 4.0))
    broker.update_resource_telemetry("a-roomy", _report(16.0, 16.0))

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="utility work",
        args=_utility_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "a-roomy"


def test_fresh_telemetry_without_explicit_hint_preserves_static_benchmark_preference():
    registry = _registry(with_requirements=False)
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("z-fast", _report(4.0, 4.0))
    broker.update_resource_telemetry("a-roomy", _report(16.0, 16.0))

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="utility work",
        args=_utility_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "z-fast"


def test_stale_resource_measurement_does_not_enforce_fit_hint():
    registry = _registry()
    broker = DeviceTaskBroker(resource_ttl_seconds=10.0)
    stale_report = sanitize_resource_telemetry(_report(4.0, 4.0))
    broker._resources["z-fast"] = (monotonic() - 20.0, stale_report)
    broker._resources["a-roomy"] = (monotonic() - 20.0, sanitize_resource_telemetry(_report(16.0, 16.0)))

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="utility work",
        args=_utility_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "z-fast"


def test_explicit_fit_keeps_faster_node_when_capacity_is_sufficient():
    registry = NodeRegistry()
    registry.register(_node("a-slow", 900.0, required_gib=2.0))
    registry.register(_node("z-fast", 300.0, required_gib=2.0))
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("z-fast", _report(4.0, 3.0))
    broker.update_resource_telemetry("a-slow", _report(16.0, 15.0))

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="utility work",
        args=_utility_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "z-fast"


def test_all_explicitly_measured_no_fit_nodes_fail_without_dispatch():
    registry = NodeRegistry()
    registry.register(_node("node-a", 300.0, required_gib=8.0))
    registry.register(_node("node-b", 400.0, required_gib=12.0))
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("node-a", _report(4.0, 4.0))
    broker.update_resource_telemetry("node-b", _report(6.0, 6.0))

    with pytest.raises(LookupError, match="measured accelerator capacity"):
        broker.enqueue(
            registry,
            capability="llm.ollama",
            intent="utility work",
            args=_utility_args(),
            requester_device_id="creator",
        )

    assert broker.snapshot()["tasks"] == []


def test_apple_unified_memory_can_satisfy_explicit_accelerator_fit():
    registry = NodeRegistry()
    registry.register(_node("m1", 500.0, required_gib=8.0))
    scheduler = HomeComputeScheduler(registry)
    scheduler.update_load(NodeLoad(
        node_id="m1",
        memory_fraction=0.375,
        accelerator_fraction=0.375,
        memory_total_gib=16.0,
        memory_free_gib=10.0,
        accelerator_total_gib=16.0,
        accelerator_free_gib=10.0,
        unified_memory=True,
    ))

    selected = scheduler.choose(WorkloadRequest(
        capability="llm.ollama",
        operation="utility",
        local_preferred=True,
    ))

    assert selected is not None
    assert selected.node_id == "m1"


def test_unroutable_node_is_not_resurrected_by_large_resource_capacity():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="disabled",
        role="capability_node",
        host_type="capability_node",
        platform="test",
        capabilities={
            "llm.ollama": CapabilityDescriptor(
                "llm.ollama",
                available=False,
                readiness="unavailable",
                private=True,
                local=True,
                metadata={"resource_accelerator_gib_utility": 1.0},
            )
        },
    ))
    registry.register(_node("eligible", 600.0, required_gib=2.0))
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("disabled", _report(48.0, 48.0))
    broker.update_resource_telemetry("eligible", _report(8.0, 8.0))

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="utility work",
        args=_utility_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "eligible"


def test_explicit_resource_requirements_use_fixed_role_keys_only(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB", "3.5")
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION", "5")
    capabilities = [
        CapabilityDescriptor("llm.ollama", metadata={"existing": "kept"}),
        CapabilityDescriptor("personal_search", metadata={"existing": "untouched"}),
    ]

    projected = apply_explicit_resource_requirements(capabilities)
    metadata = projected[0].metadata
    assert metadata["existing"] == "kept"
    assert metadata["resource_accelerator_gib_general"] == 3.5
    assert metadata["resource_accelerator_gib_conversation"] == 5.0
    assert metadata["resource_accelerator_gib_fast"] == 3.5
    assert metadata["resource_accelerator_gib_utility"] == 3.5
    assert projected[1].metadata == {"existing": "untouched"}


class _RegistrationGateway:
    def __init__(self):
        self.device_id = "node-a"
        self.registration = None

    def register_node(self, **kwargs):
        self.registration = kwargs
        return {"ok": True}


def test_production_resource_gateway_projects_fit_hints_at_registration(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_UTILITY", "6.25")
    gateway = _RegistrationGateway()
    wrapped = ResourceReportingGateway(gateway, observer=lambda: object())
    descriptor = CapabilityDescriptor("llm.ollama", private=True, local=True, cost="local")

    response = wrapped.register_node(
        display_name="Node A",
        host_type="capability_node",
        platform="windows",
        surface="home_node",
        capabilities=[descriptor.to_dict()],
        local=True,
    )

    assert response["ok"] is True
    metadata = gateway.registration["capabilities"][0]["metadata"]
    assert metadata == {"resource_accelerator_gib_utility": 6.25}
