from __future__ import annotations

import json

import pytest

from mary.core.mary import Mary
from mary.runtime.application import create_application


def _observe_positive(
    mary: Mary,
    name: str,
    index: int,
    *,
    category: str = "music",
) -> dict:
    return mary.observe_preference_experience(
        name,
        category=category,
        strength=0.80,
        polarity=1.0,
        confidence=0.90,
        source="experience",
        reason=f"consistent experience {index}",
        evidence_id=f"experience-{index}",
    )


def test_plain_mary_keeps_preference_promotion_persistence_unconfigured(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    assert mary.preference_promotion.configured is False
    assert mary.preference_promotion.path is None


def test_model_output_cannot_count_as_preference_evidence(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    with pytest.raises(ValueError):
        mary.observe_preference_experience(
            "lavender candles",
            source="model_dialogue",
            confidence=1.0,
        )

    assert mary.preference_promotion.get_candidate("lavender candles") is None
    assert mary.preferences.get_preference("lavender candles") is None


def test_single_observation_never_promotes_or_mutates_preferences(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    evaluation = _observe_positive(mary, "late-night jazz", 1)

    assert evaluation["observation_count"] == 1
    assert evaluation["eligible"] is False
    assert mary.preferences.get_preference("late-night jazz") is None


def test_repeated_consistent_evidence_becomes_eligible_but_does_not_auto_promote(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    _observe_positive(mary, "late-night jazz", 1)
    _observe_positive(mary, "late-night jazz", 2)
    evaluation = _observe_positive(mary, "late-night jazz", 3)

    assert evaluation["eligible"] is True
    assert evaluation["observation_count"] == 3
    assert evaluation["consistency"] == pytest.approx(1.0)
    assert mary.preferences.get_preference("late-night jazz") is None


def test_duplicate_evidence_id_does_not_inflate_candidate(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    first = mary.observe_preference_experience(
        "rainy cafes",
        category="places",
        strength=0.8,
        polarity=1.0,
        confidence=0.9,
        source="experience",
        evidence_id="same-event",
    )
    second = mary.observe_preference_experience(
        "rainy cafes",
        category="places",
        strength=0.8,
        polarity=1.0,
        confidence=0.9,
        source="experience",
        evidence_id="same-event",
    )

    assert first["observation_count"] == 1
    assert second["observation_count"] == 1


def test_explicit_promotion_creates_developed_preference(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    for index in range(1, 4):
        _observe_positive(mary, "late-night jazz", index)

    result = mary.promote_preference_candidate("late-night jazz")

    assert result["promoted"] is True
    preference = mary.preferences.get_preference("late-night jazz")
    assert preference is not None
    assert preference["source"] == "experience_promotion"
    assert preference["polarity"] == 1.0
    assert preference["strength"] == pytest.approx(0.8)
    assert mary.preference_promotion.get_candidate("late-night jazz") is None
    assert mary.preference_promotion.get_history()[-1]["status"] == "promoted"


def test_canonical_authored_preference_cannot_be_overwritten_by_promotion(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    canonical = mary.preferences.get_preference("drawing")
    assert canonical is not None
    assert canonical["source"] == "character_core"

    for index in range(1, 4):
        mary.observe_preference_experience(
            "drawing",
            category="creative",
            strength=0.95,
            polarity=-1.0,
            confidence=0.95,
            source="experience",
            evidence_id=f"drawing-{index}",
        )

    result = mary.promote_preference_candidate("drawing")
    after = mary.preferences.get_preference("drawing")

    assert result["promoted"] is False
    assert "canonical" in result["reason"].lower()
    assert after is not None
    assert after["source"] == "character_core"
    assert after["polarity"] == canonical["polarity"]
    assert after["strength"] == canonical["strength"]


def test_candidate_evidence_survives_restart_but_is_not_self_state_until_promoted(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    memory_path = tmp_path / "memory" / "memory.json"
    developed_path = tmp_path / "personality" / "developed_self.json"
    promotion_path = tmp_path / "personality" / "preference_promotion.json"

    first = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        preference_promotion_path=promotion_path,
        auto_save=True,
    )

    _observe_positive(first.mary, "late-night jazz", 1)
    _observe_positive(first.mary, "late-night jazz", 2)

    assert first.mary.preferences.get_preference("late-night jazz") is None
    assert promotion_path.exists()
    first.close()

    raw = json.loads(promotion_path.read_text(encoding="utf-8"))
    assert "late-night jazz" in raw["candidates"]
    assert raw["policy"]["auto_promote"] is False
    assert raw["policy"]["model_output_counts_as_evidence"] is False

    second = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        preference_promotion_path=promotion_path,
        auto_save=True,
    )

    assert second.mary.preferences.get_preference("late-night jazz") is None
    restored = second.mary.evaluate_preference_candidate("late-night jazz")
    assert restored["observation_count"] == 2
    assert restored["eligible"] is False

    final_eval = _observe_positive(second.mary, "late-night jazz", 3)
    assert final_eval["eligible"] is True
    assert second.mary.preferences.get_preference("late-night jazz") is None

    promoted = second.mary.promote_preference_candidate("late-night jazz")
    assert promoted["promoted"] is True
    second.close()

    third = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        preference_promotion_path=promotion_path,
        auto_save=True,
    )

    restored_preference = third.mary.preferences.get_preference("late-night jazz")
    assert restored_preference is not None
    assert restored_preference["source"] == "experience_promotion"
    assert third.mary.preference_promotion.get_candidate("late-night jazz") is None
    third.close()
