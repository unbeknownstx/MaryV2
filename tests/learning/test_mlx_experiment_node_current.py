from pathlib import Path
from types import SimpleNamespace

from mary.distributed.capabilities import CapabilityDescriptor
from mary.distributed.permissions import DeviceExecutionPermissions
from mary.core.service import MaryCoreService


ROOT = Path(__file__).resolve().parents[2]


def test_mlx_lm_requires_explicit_device_permission(tmp_path):
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    assert "llm.mlx_lm" in permissions.status()["supported"]
    assert not permissions.is_allowed("llm.mlx_lm")
    permissions.allow("llm.mlx_lm")
    assert permissions.is_allowed("llm.mlx_lm")
    permissions.deny("llm.mlx_lm")
    assert not permissions.is_allowed("llm.mlx_lm")


def test_trial_node_projection_accepts_exact_mlx_runtime_evidence():
    capability = CapabilityDescriptor(
        name="llm.mlx_lm",
        private=True,
        local=True,
        cost="local",
        metadata={
            "runtime": "mlx_lm",
            "configured_model": "mlx-community/Qwen3-1.7B-4bit",
            "artifact_fingerprint": "mlx-artifact-exact",
            "model_experiment_id": "model_exp_test",
            "model_experiment_trial_ready": True,
            "model_experiment_benchmark_verified": True,
            "model_experiment_benchmark_fingerprint": "marybench-test-v1",
            "model_experiment_benchmark_case_count": 60,
            "model_experiment_runtime_match": True,
            "model_experiment_artifact_match": True,
            "model_experiment_node_match": True,
            "model_experiment_mary_fit": 0.91,
            "model_experiment_latency_ms": 125.0,
            "execution_authorized": True,
        },
    )
    node = SimpleNamespace(
        node_id="MAC-MARY",
        capabilities={"llm.mlx_lm": capability},
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        node_registry=SimpleNamespace(available=lambda: [node])
    )
    record = SimpleNamespace(
        id="model_exp_test",
        runtime="mlx_lm",
        model="mlx-community/Qwen3-1.7B-4bit",
        artifact_fingerprint="mlx-artifact-exact",
        node_id="MAC-MARY",
        benchmark_fingerprint="marybench-test-v1",
        benchmark_case_count=60,
        benchmark_verified=True,
        trial_ready=True,
    )
    service._model_experiment_ledger = lambda: SimpleNamespace(
        get=lambda experiment_id: record if experiment_id == "model_exp_test" else (_ for _ in ()).throw(KeyError(experiment_id))
    )

    rows = service._model_experiment_trial_nodes("model_exp_test")
    assert len(rows) == 1
    assert rows[0]["capability"] == "llm.mlx_lm"
    assert rows[0]["runtime"] == "mlx_lm"
    assert rows[0]["core_registered"] is True
    assert rows[0]["core_trial_ready"] is True
    assert rows[0]["runnable"] is True


def test_mlx_executor_stays_bounded_to_reviewed_bundle_and_experiment():
    source = (ROOT / "mary/desktop/device_node.py").read_text(encoding="utf-8")
    core = (ROOT / "mary/core/service.py").read_text(encoding="utf-8")

    assert 'MARY_MLX_EXPERIMENT_BUNDLE' in source
    assert 'MARY_MLX_EXPERIMENT_ID' in source
    assert 'build_mlx_adapter_candidate_proposal' in source
    assert 'adapter_path=str(bundle / "adapter")' in source
    assert 'requested_experiment != expected_experiment' in source
    assert 'elif capability == "llm.mlx_lm"' in source

    assert 'for capability_name in ("llm.llama_cpp", "llm.mlx_lm")' in core
    assert 'capability=str(selected.get("capability") or "llm.llama_cpp")' in core
    assert '"experiment_id": experiment_id' in core
    assert '"production_route_changed": False' in core
    assert '"promotion_performed": False' in core


def test_locally_ready_mlx_node_is_not_runnable_until_core_knows_experiment():
    capability = CapabilityDescriptor(
        name="llm.mlx_lm",
        private=True,
        local=True,
        cost="local",
        metadata={
            "runtime": "mlx_lm",
            "configured_model": "mlx-community/Qwen3-1.7B-4bit",
            "artifact_fingerprint": "mlx-artifact-exact",
            "model_experiment_id": "model_exp_node_only",
            "model_experiment_trial_ready": True,
            "model_experiment_benchmark_verified": True,
            "model_experiment_benchmark_fingerprint": "marybench-test-v1",
            "model_experiment_benchmark_case_count": 60,
            "model_experiment_runtime_match": True,
            "model_experiment_artifact_match": True,
            "model_experiment_node_match": True,
            "execution_authorized": True,
        },
    )
    node = SimpleNamespace(
        node_id="MAC-MARY",
        capabilities={"llm.mlx_lm": capability},
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        node_registry=SimpleNamespace(available=lambda: [node])
    )
    service._model_experiment_ledger = lambda: SimpleNamespace(
        get=lambda experiment_id: (_ for _ in ()).throw(KeyError(experiment_id))
    )

    row = service._model_experiment_trial_nodes("model_exp_node_only")[0]
    assert row["node_trial_ready"] is True
    assert row["core_registered"] is False
    assert row["core_trial_ready"] is False
    assert row["registration_required"] is True
    assert row["runnable"] is False
