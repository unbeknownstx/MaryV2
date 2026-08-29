from __future__ import annotations

import json

from mary.training import MaryTrainingDatasetExporter, ResponseFeedbackStore


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_explicit_positive_and_creator_correction_export_to_distinct_training_surfaces(tmp_path):
    store = ResponseFeedbackStore(tmp_path / "feedback.json")
    store.record(
        rating="positive",
        user_text="I finally got it working.",
        assistant_text="Hell yeah. We got there.",
        provider="local_character_mind",
        model="local_composer_v2",
        performance_context="private",
        tags=["felt_like_mary"],
    )
    store.record(
        rating="negative",
        user_text="What do you think about capability and authority?",
        assistant_text="Capability is a right.",
        chosen_text="Being capable of something doesn't make it yours to decide.",
        provider="groq",
        model="test",
        character_patterns=["authority_or_control", "philosophical_exchange"],
        tags=["did_not_feel_like_mary", "character_inversion"],
    )

    out = tmp_path / "dataset"
    summary = MaryTrainingDatasetExporter().export(store, out)
    assert summary.source_records == 2
    assert summary.sft == 2  # approved response + creator correction
    assert summary.preferences == 1
    assert summary.rejected == 1
    assert summary.eval == 2

    sft = _rows(out / "mary_sft.jsonl")
    prefs = _rows(out / "mary_preferences.jsonl")
    rejected = _rows(out / "mary_rejected.jsonl")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    assert any(row["messages"][-1]["content"] == "Hell yeah. We got there." for row in sft)
    assert prefs[0]["chosen"].startswith("Being capable")
    assert prefs[0]["rejected"] == "Capability is a right."
    assert rejected[0]["response"] == "Capability is a right."
    assert manifest["policy"]["ordinary_conversation_harvested"] is False
    assert manifest["policy"]["feedback_is_character_authority"] is False
    assert manifest["policy"]["training_performed"] is False


def test_mary_initiative_feedback_uses_grounded_context_without_fabricating_creator_speech(tmp_path):
    store = ResponseFeedbackStore(tmp_path / "feedback.json")
    store.record(
        rating="positive",
        user_text="",
        context_text="Project event: the full verification suite became green.",
        assistant_text="Okay, that's a W.",
        source_kind="mary_initiative",
        input_authority="environment_context_only",
        tags=["felt_like_mary", "good_timing"],
    )

    out = tmp_path / "dataset"
    MaryTrainingDatasetExporter().export(store, out)
    row = _rows(out / "mary_sft.jsonl")[0]
    assert row["source_kind"] == "mary_initiative"
    assert row["input_authority"] == "environment_context_only"
    assert row["messages"][0]["role"] == "system"
    assert "not creator-authored speech" in row["messages"][0]["content"]
    assert "Project event" in row["messages"][1]["content"]


def test_training_dataset_preview_is_read_only_and_counts_explicit_feedback(tmp_path):
    store = ResponseFeedbackStore(tmp_path / "feedback_preview.json")
    store.record(rating="positive", user_text="Hi", assistant_text="Hey.")
    store.record(rating="negative", user_text="No", assistant_text="Wrong", chosen_text="Better")
    preview = MaryTrainingDatasetExporter().preview(store)
    assert preview["source_records"] == 2
    assert preview["sft_candidates"] == 2
    assert preview["preference_candidates"] == 1
    assert preview["rejected_candidates"] == 1
    assert preview["writes_files"] is False
    assert preview["trains_model"] is False
