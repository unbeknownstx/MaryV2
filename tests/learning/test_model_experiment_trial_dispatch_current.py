from threading import RLock
from types import SimpleNamespace
import pytest
from mary.core.service import MaryCoreService
from mary.distributed.capabilities import CapabilityDescriptor
from mary.distributed.nodes import NodeDescriptor, NodeRegistry
from mary.protocol.models import RuntimeActionRequest

def _registry(*, authorized=True, trial_ready=True):
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="mac-m1", display_name="Mac M1", role="compute",
        host_type="mac", platform="macos",
        capabilities={"llm.llama_cpp": CapabilityDescriptor(
            name="llm.llama_cpp", available=True, private=True, local=True,
            cost="local", readiness="ready", metadata={
                "runtime":"llama.cpp","configured_model":"reviewed-model",
                "execution_authorized":authorized,
                "model_experiment_id":"model_exp_exact",
                "model_experiment_runtime_match":True,
                "model_experiment_artifact_match":True,
                "model_experiment_node_match":True,
                "model_experiment_trial_ready":trial_ready,
                "model_experiment_mary_fit":0.91,
                "model_experiment_latency_ms":640.0,
                "model_experiment_benchmark_verified":True,
            })},
    ))
    return registry

class _Task:
    task_id="trial_task"
    def to_dict(self): return {"task_id":self.task_id,"capability":"llm.llama_cpp","selected_node_id":"mac-m1","status":"queued"}

class _Broker:
    def __init__(self): self.calls=[]
    def enqueue(self, registry, **kwargs):
        self.calls.append(kwargs)
        assert registry.get(kwargs["preferred_node_id"]) is not None
        return _Task()

def _core(registry):
    core=object.__new__(MaryCoreService)
    core._closed=False
    core._turn_lock=RLock()
    core.mary=SimpleNamespace(node_registry=registry)
    core.device_tasks=_Broker()
    return core

def test_exact_benchmark_evidence_is_required_for_trial():
    core=_core(_registry())
    row=core._model_experiment_trial_nodes("model_exp_exact")[0]
    assert row["trial_ready"] is True and row["runnable"] is True
    assert _core(_registry(trial_ready=False))._model_experiment_trial_nodes("model_exp_exact")[0]["runnable"] is False

def test_explicit_trial_targets_exact_node_and_utility_lane():
    core=_core(_registry())
    result=core.runtime_action(RuntimeActionRequest.from_dict({
        "action":"model.experiment.dispatch","device_id":"creator-test",
        "args":{"experiment_id":"model_exp_exact","prompt":"held-out prompt","max_tokens":200},
    }))
    assert result["task"]["selected_node_id"]=="mac-m1"
    assert result["production_route_changed"] is False
    assert result["promotion_performed"] is False
    call=core.device_tasks.calls[0]
    assert call["preferred_node_id"]=="mac-m1"
    assert call["capability"]=="llm.llama_cpp"
    assert call["args"]["experiment_id"]=="model_exp_exact"
    assert call["args"]["role"]=="utility"
    assert "canonical Mary" in call["args"]["messages"][0]["content"]

def test_explicit_trial_fails_closed_without_local_permission():
    core=_core(_registry(authorized=False))
    with pytest.raises(PermissionError):
        core.runtime_action(RuntimeActionRequest.from_dict({
            "action":"model.experiment.dispatch","device_id":"creator-test",
            "args":{"experiment_id":"model_exp_exact","prompt":"test"},
        }))
    assert core.device_tasks.calls==[]
