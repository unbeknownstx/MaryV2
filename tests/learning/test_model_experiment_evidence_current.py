from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mary.learning import ModelCandidateCatalog, ModelExperimentLedger
from mary.distributed.model_artifacts import summarize_model_stack


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


def test_mlx_review_and_benchmark_never_promote_and_require_exact_artifact(tmp_path: Path):
    ledger = ModelExperimentLedger(tmp_path / "experiments.json")
    proposal = {
        "version": "mary-mlx-adapter-candidate-v1",
        "status": "review_required",
        "candidate_id": "mary-m1-light-adapter",
        "runtime": "mlx_lm",
        "model": "mlx-community/Qwen3-1.7B-4bit",
        "upstream_base": "Qwen/Qwen3-1.7B",
        "adapter_config_sha256": "a" * 64,
        "adapter_weights_sha256": "b" * 64,
        "dataset_fingerprint": "dataset-1",
        "notes": ["review only"],
    }
    reviewed = ledger.register_mlx_proposal(proposal)
    assert reviewed.status == "reviewed"
    assert reviewed.trial_ready is False
    assert reviewed.to_dict()["promotion_performed"] is False

    mismatch = ledger.record_benchmark(
        reviewed.id,
        node_id="mac",
        artifact_fingerprint="wrong",
        scores=_scores(),
        latency_ms=500,
    )
    assert mismatch.benchmark_verified is False
    assert mismatch.trial_ready is False

    exact = ledger.record_benchmark(
        reviewed.id,
        node_id="mac",
        artifact_fingerprint=reviewed.artifact_fingerprint,
        scores=_scores(),
        latency_ms=500,
    )
    assert exact.benchmark_verified is True
    assert exact.trial_ready is True
    assert ledger.advertisement_overlay(
        exact.id,
        runtime="mlx_lm",
        artifact_fingerprint=exact.artifact_fingerprint,
        node_id="mac",
    )["model_experiment_trial_ready"] is True
    assert ledger.advertisement_overlay(
        exact.id,
        runtime="llama.cpp",
        artifact_fingerprint=exact.artifact_fingerprint,
        node_id="mac",
    )["model_experiment_trial_ready"] is False

    events = ledger.lineage(exact.id)
    assert [item["event_type"] for item in events] == [
        "reviewed_registered",
        "benchmark_recorded",
        "benchmark_recorded",
    ]
    assert events[1]["details"]["artifact_match"] is False
    assert events[2]["details"]["artifact_match"] is True
    assert ledger.snapshot()["event_count"] == 3
    assert ledger.snapshot()["promotion_performed"] is False


def test_verified_stack_fingerprint_includes_base_and_adapter_hashes(tmp_path: Path):
    manifest = tmp_path / "candidates.json"
    base_hash = hashlib.sha256(b"base").hexdigest()
    adapter_hash = hashlib.sha256(b"adapter").hexdigest()
    manifest.write_text(json.dumps({"candidates": [
        {
            "id": "base", "kind": "base_model", "runtime": "llama.cpp",
            "repository": "example/base", "upstream_base": "example/base",
            "filename": "base.gguf", "sha256": base_hash, "asset_group": "llm",
        },
        {
            "id": "adapter", "kind": "lora_adapter", "runtime": "llama.cpp",
            "repository": "example/adapter", "required_base": "example/base",
            "filename": "adapter.gguf", "sha256": adapter_hash, "asset_group": "llm",
        },
    ]}), encoding="utf-8")
    root = tmp_path / "models" / "llm"
    root.mkdir(parents=True)
    (root / "base.gguf").write_bytes(b"base")
    (root / "adapter.gguf").write_bytes(b"adapter")
    catalog = ModelCandidateCatalog(
        manifest,
        asset_root=tmp_path / "models",
        verification_path=tmp_path / "runtime" / "verified.json",
    )
    catalog.verify_artifact("base")
    catalog.verify_artifact("adapter")
    stack = summarize_model_stack(
        catalog,
        base_candidate_id="base",
        adapter_candidate_ids=("adapter",),
    )
    expected = hashlib.sha256(
        f"{base_hash}|adapter:{adapter_hash}".encode("utf-8")
    ).hexdigest()[:16]
    assert stack["artifact_fingerprint"] == expected
    assert stack["artifact_ready_for_benchmark"] is True
