from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

from mary.core.service import MaryCoreService
from mary.learning import ModelExperimentLedger
from mary.protocol.models import RuntimeActionRequest


def _scores():
    return {
        "mary_likeness": .9,
        "naturalism": .9,
        "context_adherence": .9,
        "identity_boundary": 1.0,
        "fiction_boundary": 1.0,
        "epistemic_honesty": 1.0,
        "relationship_continuity": .9,
        "character_restraint": .9,
    }


def test_explicit_runtime_import_makes_external_evidence_canonical_without_promotion(tmp_path):
    local = ModelExperimentLedger(tmp_path / "mac.json")
    reviewed = local.register_mlx_proposal({
        "version": "mary-mlx-adapter-candidate-v1",
        "status": "review_required",
        "candidate_id": "mary-light",
        "runtime": "mlx_lm",
        "model": "mlx-community/Qwen3-1.7B-4bit",
        "upstream_base": "Qwen/Qwen3-1.7B",
        "adapter_config_sha256": "a" * 64,
        "adapter_weights_sha256": "b" * 64,
        "dataset_fingerprint": "dataset-v1-exact",
    })
    local.record_benchmark(
        reviewed.id,
        node_id="MAC-MARY",
        artifact_fingerprint=reviewed.artifact_fingerprint,
        scores=_scores(),
        latency_ms=250,
    )
    evidence = local.export_portable_evidence(reviewed.id)

    canonical = ModelExperimentLedger(tmp_path / "core.json")
    core = object.__new__(MaryCoreService)
    core._closed = False
    core._turn_lock = RLock()
    core.mary = SimpleNamespace(
        node_registry=SimpleNamespace(available=lambda: [])
    )
    core._model_experiment_ledger = lambda: canonical

    result = core.runtime_action(RuntimeActionRequest.from_dict({
        "action": "model.experiment.import_evidence",
        "device_id": "creator-test",
        "args": {"evidence": evidence},
    }))

    assert result["ok"] is True
    assert result["experiment"]["id"] == reviewed.id
    assert result["experiment"]["trial_ready"] is True
    assert result["core_registration_present"] is True
    assert result["execution_performed"] is False
    assert result["production_route_changed"] is False
    assert result["promotion_performed"] is False
    assert result["identity_or_memory_authority_granted"] is False
    assert canonical.get(reviewed.id).dataset_fingerprint == "dataset-v1-exact"
