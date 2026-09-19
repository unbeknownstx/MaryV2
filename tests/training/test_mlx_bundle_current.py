from __future__ import annotations

import json
from pathlib import Path

from mary.training.mlx_bundle import PROFILES, prepare_mlx_bundle


def test_mlx_profiles_pin_exact_qwen_lineage():
    assert PROFILES["m1-smoke"].model == "mlx-community/Qwen3-0.6B-4bit"
    assert PROFILES["m1-smoke"].upstream_base == "Qwen/Qwen3-0.6B"
    assert PROFILES["m1-smoke"].experiment_class == "pipeline_smoke"
    assert PROFILES["m1-smoke"].lora_rank == 4
    assert PROFILES["m1-light"].model == "mlx-community/Qwen3-1.7B-4bit"
    assert PROFILES["m1-light"].upstream_base == "Qwen/Qwen3-1.7B"
    assert PROFILES["m1-4b"].model == "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    assert PROFILES["m1-4b"].upstream_base == "Qwen/Qwen3-4B-Instruct-2507"


def test_prepare_mlx_bundle_uses_only_structured_approved_mary_sft(tmp_path: Path):
    root = tmp_path / "repo"
    active = root / "character_sources" / "active"
    active.mkdir(parents=True)

    rows = []
    for index in range(24):
        rows.append({
            "heading": f"TEST-{index}",
            "labels": ["DNA"],
            "text": (
                f"Situation: Unbe asks Mary about test situation {index}. "
                f"Mary behavior: Answer directly in a grounded Mary-consistent way {index}. "
                "Avoid: Generic assistant closers. "
                "Source/provenance: creator-authored test fixture. Strength: 1.0."
            ),
        })
    (active / "mary_behavior_fixture.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    output = tmp_path / "bundle"
    manifest = prepare_mlx_bundle(
        root=root,
        output_dir=output,
        profile_id="m1-light",
    )

    assert manifest["boundaries"]["training_performed"] is False
    assert manifest["dataset_fingerprint"] == manifest["mary_dataset"]["fingerprint"]
    assert manifest["boundaries"]["marybench_in_training_data"] is False
    assert manifest["boundaries"]["dataset_quality_gate_passed"] is True
    assert manifest["dataset_audit"]["training_ready"] is True
    assert manifest["dataset_audit"]["marybench_prompt_leaks"] == 0
    assert manifest["dataset_audit"]["split_leakage_groups"] == 0
    assert manifest["boundaries"]["ordinary_conversation_harvested"] is False
    assert manifest["boundaries"]["exact_base_required"] is True
    assert manifest["examples"]["behavior"] == 24
    assert manifest["training_readiness"]["dataset_ready"] is True
    assert manifest["training_readiness"]["ready_for_training"] is False
    assert manifest["training_readiness"]["manual_creator_gate_required"] is True
    assert manifest["examples"]["train"] > 0

    train = [
        json.loads(line)
        for line in (output / "mlx-data" / "train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert train
    assert all(set(row) == {"messages"} for row in train)
    assert all(
        any(message["role"] == "assistant" for message in row["messages"])
        for row in train
    )

    config = (output / "mlx_lora_config.yaml").read_text(encoding="utf-8")
    assert 'model: "mlx-community/Qwen3-1.7B-4bit"' in config
    assert "fine_tune_type: lora" in config
    assert "--mask-prompt" in manifest["run"]["train"]
    assert manifest["stack_matrix"]["cross_base_stacking"] == "forbidden"
    assert [item["profile_id"] for item in manifest["experiment_ladder"]] == [
        "m1-smoke", "m1-light", "m1-4b"
    ]
    assert "mlx_lm.generate" in manifest["run"]["generate_smoke"]


def test_prepare_mlx_bundle_forwards_creator_reviewed_novel_abstractions(tmp_path: Path):
    root = tmp_path / "repo"
    active = root / "character_sources" / "active"
    active.mkdir(parents=True)
    rows = [
        {
            "heading": f"EX-{index}",
            "labels": ["DNA"],
            "text": (
                f"Situation: Baseline authored situation {index}. "
                f"Mary behavior: Baseline authored behavior {index}. "
                "Avoid: generic assistant drift."
            ),
        }
        for index in range(12)
    ]
    (active / "mary_behavior_fixture.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    review = tmp_path / "novel_review.json"
    review.write_text(json.dumps({
        "source": {"file": "Unbeknownst.docx", "sha256": "a" * 64},
        "reviews": [{
            "candidate_id": "scene-reviewed-1",
            "status": "approved",
            "situation": "A fictional scene reveals a generalizable pressure response.",
            "mary_behavior": "Stay practical first, then let the emotion show without claiming the scene happened to AI Mary.",
            "tags": ["pressure", "fiction-derived"],
        }],
    }), encoding="utf-8")

    output = tmp_path / "bundle"
    manifest = prepare_mlx_bundle(
        root=root,
        output_dir=output,
        profile_id="m1-light",
        novel_review_path=review,
    )

    assert manifest["mary_dataset"]["novel_behavior_sft"] == 1
    rows = [
        json.loads(line)
        for line in (output / "mary-dataset-v1" / "mary_behavior_sft.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(row["example_id"] == "novel_behavior_scene-reviewed-1" for row in rows)
    assert all("fictional scene as AI-Mary lived memory" not in json.dumps(row).casefold() for row in rows)
