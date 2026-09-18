from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mary.distributed.model_artifacts import summarize_model_stack
from mary.learning import ModelCandidateCatalog


def _catalog(tmp_path: Path) -> ModelCandidateCatalog:
    manifest = tmp_path / "candidates.json"
    manifest.write_text(json.dumps({
        "candidates": [
            {
                "id": "base",
                "kind": "base_model",
                "runtime": "llama.cpp",
                "repository": "example/base-gguf",
                "upstream_base": "example/base",
                "filename": "base.gguf",
                "sha256": hashlib.sha256(b"base").hexdigest(),
                "role": ["adapter_lab"],
                "asset_group": "llm",
            },
            {
                "id": "adapter",
                "kind": "lora_adapter",
                "runtime": "llama.cpp",
                "repository": "example/adapter",
                "filename": "adapter.gguf",
                "sha256": hashlib.sha256(b"adapter").hexdigest(),
                "required_base": "example/base",
                "role": ["adapter_lab"],
                "asset_group": "llm",
            },
        ]
    }), encoding="utf-8")
    return ModelCandidateCatalog(
        manifest,
        asset_root=tmp_path / "models",
        verification_path=tmp_path / "runtime" / "artifact_evidence.json",
    )


def test_node_model_artifact_metadata_is_fail_closed_until_verified(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    folder = tmp_path / "models" / "llm"
    folder.mkdir(parents=True)
    (folder / "base.gguf").write_bytes(b"base")
    (folder / "adapter.gguf").write_bytes(b"adapter")

    before = summarize_model_stack(
        catalog,
        base_candidate_id="base",
        adapter_candidate_ids=("adapter",),
    )
    assert before["artifact_configuration"] == "configured"
    assert before["artifact_verified"] is False
    assert before["artifact_stack_compatible"] is True
    assert before["artifact_ready_for_benchmark"] is False

    catalog.verify_artifact("base")
    catalog.verify_artifact("adapter")
    after = summarize_model_stack(
        catalog,
        base_candidate_id="base",
        adapter_candidate_ids=("adapter",),
    )
    assert after["artifact_verified"] is True
    assert after["artifact_adapters_verified"] == 1
    assert after["artifact_stack_compatible"] is True
    assert after["artifact_ready_for_benchmark"] is True
    assert len(after["artifact_fingerprint"]) == 16


def test_node_model_artifact_metadata_rejects_unknown_candidate(tmp_path: Path) -> None:
    row = summarize_model_stack(
        _catalog(tmp_path),
        base_candidate_id="missing",
        adapter_candidate_ids=(),
    )
    assert row["artifact_configuration"] == "invalid_candidate"
    assert row["artifact_ready_for_benchmark"] is False
