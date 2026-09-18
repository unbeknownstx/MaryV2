from __future__ import annotations

import json
from pathlib import Path

from mary.training import MaryDatasetV1Exporter, ResponseFeedbackStore


def _write_sources(root: Path) -> None:
    active = root / "character_sources" / "active"
    active.mkdir(parents=True)
    rows = [
        {
            "heading": "EX-001 — Evidence proves her wrong",
            "labels": ["DNA"],
            "text": (
                "Situation: A discussion ends with clear evidence against Mary's position. "
                "Mary behavior: Acknowledge it, correct the claim, learn. "
                "Performance tells: brief embarrassment before acceptance. "
                "Avoid: doubling down."
            ),
        },
        {
            "heading": "NEG-001 — Generic assistant",
            "labels": ["NEG"],
            "text": (
                "NOT MARY pattern: generic assistant opening. "
                "Correction: react to the actual content first."
            ),
        },
        {
            "heading": "FC-001 — Fictional history",
            "labels": ["FC"],
            "text": "Fictional Mary once crossed a dangerous city at night.",
        },
        {
            "heading": "AI-001 — Identity",
            "labels": ["AI"],
            "text": "The active language model is a replaceable engine, not Mary's identity.",
        },
    ]
    (active / "mary_dataset_fixture.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    evals = {
        "cases": [
            {
                "case_id": "mary_eval_direct",
                "prompt": "Hey Mary, what do you think?",
                "category": "character",
                "forbidden_phrases": ["How can I assist you today"],
            }
        ]
    }
    (root / "character_sources" / "mary_evaluation.json").write_text(
        json.dumps(evals),
        encoding="utf-8",
    )


def test_mary_dataset_v1_exports_separate_training_and_eval_surfaces(tmp_path, monkeypatch):
    monkeypatch.delenv("MARY_CHARACTER_SOURCES", raising=False)
    monkeypatch.delenv("MARY_CHARACTER_EVALS", raising=False)
    _write_sources(tmp_path)

    feedback_path = tmp_path / "data" / "training" / "response_feedback.json"
    store = ResponseFeedbackStore(feedback_path)
    store.record(
        rating="positive",
        user_text="Tell me what you think.",
        assistant_text="Yeah, that's actually kind of wild.",
        provider="local",
        model="qwen",
        tags=["felt_like_mary"],
    )
    store.record(
        rating="negative",
        user_text="How are you?",
        assistant_text="How can I assist you today?",
        chosen_text="I'm good. Kinda restless, though.",
        provider="local",
        model="qwen",
        tags=["did_not_feel_like_mary"],
    )

    output = tmp_path / "dataset"
    summary = MaryDatasetV1Exporter().export(
        root=tmp_path,
        output_dir=output,
        feedback_path=feedback_path,
    )

    assert summary.sourcebook_records == 4
    assert summary.character_training_candidates == 2
    assert summary.behavior_sft == 1
    assert summary.negative_examples == 1
    assert summary.marybench_eval == 1
    assert summary.feedback_records == 2
    assert summary.feedback_sft == 2
    assert summary.feedback_preferences == 1
    assert summary.feedback_rejected == 1

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "mary-dataset-v1"
    assert manifest["boundaries"]["ordinary_conversation_harvested"] is False
    assert manifest["boundaries"]["memory_exported"] is False
    assert manifest["boundaries"]["relationship_state_exported"] is False
    assert manifest["boundaries"]["marybench_used_for_training_by_default"] is False
    assert manifest["boundaries"]["third_party_dataset_included"] is False

    corpus = [
        json.loads(line)
        for line in (output / "mary_character_corpus.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    fictional = next(row for row in corpus if "FC" in row["labels"])
    negative = next(row for row in corpus if "NEG" in row["labels"])
    assert fictional["training_eligible"] is False
    assert fictional["boundary"] == "fictional_reference_not_lived_memory"
    assert negative["training_eligible"] is False

    behavior = [
        json.loads(line)
        for line in (output / "mary_behavior_sft.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert behavior[0]["messages"][1]["content"].startswith("A discussion ends")
    assert behavior[0]["messages"][2]["content"].startswith("Acknowledge it")

    eval_rows = [
        json.loads(line)
        for line in (output / "mary_character_eval.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert eval_rows[0]["training_eligible"] is False
    assert eval_rows[0]["purpose"] == "held_out_character_evaluation"


def test_mary_dataset_v1_without_feedback_still_builds_repo_baseline(tmp_path, monkeypatch):
    monkeypatch.delenv("MARY_CHARACTER_SOURCES", raising=False)
    monkeypatch.delenv("MARY_CHARACTER_EVALS", raising=False)
    _write_sources(tmp_path)

    output = tmp_path / "dataset"
    summary = MaryDatasetV1Exporter().export(
        root=tmp_path,
        output_dir=output,
        feedback_path=None,
    )

    assert summary.feedback_records == 0
    assert (output / "explicit_feedback" / "mary_sft.jsonl").read_text(encoding="utf-8") == ""
    assert len(summary.fingerprint) == 24
