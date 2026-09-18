from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
                "sha256": hashlib.sha256(b"base-bytes").hexdigest(),
                "license": "Apache-2.0",
                "role": ["adapter_lab"],
                "asset_group": "llm"
            },
            {
                "id": "adapter",
                "kind": "lora_adapter",
                "runtime": "llama.cpp",
                "repository": "example/adapter",
                "filename": "adapter.gguf",
                "sha256": hashlib.sha256(b"adapter-bytes").hexdigest(),
                "license": "Apache-2.0",
                "required_base": "example/base",
                "role": ["adapter_lab"],
                "asset_group": "llm"
            }
        ]
    }), encoding="utf-8")
    return ModelCandidateCatalog(
        manifest,
        asset_root=tmp_path / "models",
        verification_path=tmp_path / "artifact_evidence.json",
    )


def test_presence_never_implies_verified_or_benchmark_ready(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    folder = tmp_path / "models" / "llm"
    folder.mkdir(parents=True)
    (folder / "base.gguf").write_bytes(b"base-bytes")

    status = catalog.artifact_status("base")
    assert status["state"] == "present_unverified"
    assert status["present"] is True
    assert status["verified"] is False
    assert status["ready_for_benchmark"] is False

    snapshot = catalog.snapshot()
    base = next(row for row in snapshot["candidates"] if row["id"] == "base")
    assert base["artifact"]["state"] == "present_unverified"


def test_hash_verification_is_durable_and_invalidates_on_change(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    folder = tmp_path / "models" / "llm"
    folder.mkdir(parents=True)
    path = folder / "base.gguf"
    path.write_bytes(b"base-bytes")

    verified = catalog.verify_artifact("base")
    assert verified["state"] == "verified"
    assert verified["ready_for_benchmark"] is True

    path.write_bytes(b"changed")
    stale = catalog.artifact_status("base")
    assert stale["state"] == "present_unverified"
    assert stale["verification_stale"] is True
    assert stale["verified"] is False

    mismatch = catalog.verify_artifact("base")
    assert mismatch["state"] == "hash_mismatch"
    assert mismatch["ready_for_benchmark"] is False


def test_stack_requires_verified_exact_pair_before_benchmark(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    folder = tmp_path / "models" / "llm"
    folder.mkdir(parents=True)
    (folder / "base.gguf").write_bytes(b"base-bytes")
    (folder / "adapter.gguf").write_bytes(b"adapter-bytes")

    before = catalog.stack_status(
        base_candidate_id="base",
        adapter_candidate_ids=("adapter",),
    )
    assert before["compatible"] is True
    assert before["artifacts_verified"] is False
    assert before["ready_for_benchmark"] is False
    assert before["ready_for_promotion"] is False

    catalog.verify_artifact("base")
    catalog.verify_artifact("adapter")
    after = catalog.stack_status(
        base_candidate_id="base",
        adapter_candidate_ids=("adapter",),
    )
    assert after["compatible"] is True
    assert after["artifacts_verified"] is True
    assert after["ready_for_benchmark"] is True
    assert after["ready_for_promotion"] is False
