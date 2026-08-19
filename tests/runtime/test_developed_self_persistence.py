from __future__ import annotations

import json

import pytest

from mary.core.mary import Mary
from mary.runtime.application import create_application


def test_plain_mary_keeps_developed_self_persistence_unconfigured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    assert mary.developed_self_state.configured is False
    assert mary.developed_self_state.path is None
    assert not (tmp_path / "developed_self.json").exists()


def test_personality_development_is_wired_to_live_self_objects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    assert mary.personality_development.personality is mary.personality
    assert mary.personality_development.values is mary.values
    assert mary.personality_development.preferences is mary.preferences


def test_authored_character_preferences_are_not_duplicated_as_developed_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    payload = mary.developed_self_state.to_dict()

    assert payload["preference_overrides"] == {}
    assert all(
        preference.get("source") != "character_core"
        for preference in payload["preference_overrides"].values()
    )


def test_experience_preference_survives_persistent_runtime_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"
    developed_path = tmp_path / "personality" / "developed_self.json"

    first = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        auto_save=True,
    )
    first.mary.set_developed_preference(
        "late-night jazz",
        category="music",
        strength=0.82,
        polarity=1.0,
        confidence=0.91,
        source="experience",
    )
    assert developed_path.exists()
    first.close()

    raw = json.loads(developed_path.read_text(encoding="utf-8"))
    assert "late-night jazz" in raw["preference_overrides"]
    assert all(
        item.get("source") != "character_core"
        for item in raw["preference_overrides"].values()
    )

    second = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        auto_save=True,
    )
    restored = second.mary.preferences.get_preference("late-night jazz")

    assert restored is not None
    assert restored["source"] == "experience"
    assert restored["strength"] == pytest.approx(0.82)
    assert second.mary.self_model.preferences is second.mary.preferences
    second.close()


def test_model_output_cannot_be_used_as_durable_preference_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    with pytest.raises(ValueError):
        mary.set_developed_preference(
            "invented favorite",
            source="model_dialogue",
        )

    assert mary.preferences.get_preference("invented favorite") is None


def test_application_close_saves_both_memory_and_developed_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"
    developed_path = tmp_path / "personality" / "developed_self.json"

    app = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
    )
    app.mary.set_developed_preference(
        "quiet bookstores",
        category="places",
        strength=0.74,
        source="experience",
    )

    assert not developed_path.exists()
    assert app.close() is True
    assert memory_path.exists()
    assert developed_path.exists()


def test_approved_personality_trait_restores_exact_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"
    developed_path = tmp_path / "personality" / "developed_self.json"

    first = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        auto_save=True,
    )

    # Simulate the exact state immediately after PersonalityDevelopment.apply()
    # succeeds. Mary.apply_personality_change() performs this record step
    # automatically in production.
    target = 0.61
    first.mary.personality.set_trait("warmth", target)
    first.mary.developed_self_state.record_approved_personality_change(
        {"trait": "warmth", "source": "approved_test"}
    )
    first.close()

    second = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        auto_save=True,
    )

    assert second.mary.personality.get_trait("warmth") == pytest.approx(target)
    second.close()
