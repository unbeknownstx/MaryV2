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
    capability="llm.llama_cpp"
    selected_node_id="mac-m1"
    status="queued"
    result={}
    error=""
    def to_dict(self): return {"task_id":self.task_id,"capability":self.capability,"selected_node_id":self.selected_node_id,"status":self.status,"result":dict(self.result),"error":self.error}

class _Broker:
    def __init__(self):
        self.calls=[]
        self.task=_Task()
    def enqueue(self, registry, **kwargs):
        self.calls.append(kwargs)
        assert registry.get(kwargs["preferred_node_id"]) is not None
        return self.task
    def get(self, task_id):
        return self.task if task_id == self.task.task_id else None

class _Ledger:
    def __init__(self): self.events=[]
    def record_trial_dispatch(self, experiment_id, **kwargs):
        self.events.append(("dispatch", experiment_id, dict(kwargs)))
    def record_trial_outcome(self, experiment_id, **kwargs):
        self.events.append(("outcome", experiment_id, dict(kwargs)))

def _core(registry):
    core=object.__new__(MaryCoreService)
    core._closed=False
    core._turn_lock=RLock()
    core.mary=SimpleNamespace(node_registry=registry)
    core.device_tasks=_Broker()
    core._model_experiment_tasks={}
    core._model_experiment_terminal_recorded=set()
    core._perception_asset_tasks={}
    core._continuity_task_links={}
    core.perception_assets=SimpleNamespace(get=lambda _asset_id: None)
    core._settle_continuity_task_link=lambda _task: None
    ledger=_Ledger()
    core._model_experiment_ledger=lambda: ledger
    core._test_ledger=ledger
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
    assert result["experiment_lineage_recorded"] is True
    assert core._model_experiment_tasks["trial_task"] == "model_exp_exact"
    assert core._test_ledger.events[0][0] == "dispatch"
    assert "held-out prompt" not in repr(core._test_ledger.events[0])

def test_explicit_trial_fails_closed_without_local_permission():
    core=_core(_registry(authorized=False))
    with pytest.raises(PermissionError):
        core.runtime_action(RuntimeActionRequest.from_dict({
            "action":"model.experiment.dispatch","device_id":"creator-test",
            "args":{"experiment_id":"model_exp_exact","prompt":"test"},
        }))
    assert core.device_tasks.calls==[]


def test_terminal_trial_status_records_outcome_once_without_prompt_or_output():
    core=_core(_registry())
    core.runtime_action(RuntimeActionRequest.from_dict({
        "action":"model.experiment.dispatch","device_id":"creator-test",
        "args":{"experiment_id":"model_exp_exact","prompt":"private held-out prompt"},
    }))
    task=core.device_tasks.task
    task.status="completed"
    task.result={"provider":"llama.cpp","model":"reviewed-model","content":"generated trial text"}

    first=core.capability_task_status(task.task_id)
    second=core.capability_task_status(task.task_id)

    outcomes=[event for event in core._test_ledger.events if event[0]=="outcome"]
    assert len(outcomes)==1
    assert outcomes[0][2]["status"]=="completed"
    assert outcomes[0][2]["provider"]=="llama.cpp"
    assert "private held-out prompt" not in repr(outcomes[0])
    assert "generated trial text" not in repr(outcomes[0])
    assert first["experiment_lineage_recorded"] is True
    assert second["experiment_lineage_recorded"] is True
