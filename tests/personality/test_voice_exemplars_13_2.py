from __future__ import annotations

from mary.personality.voice_exemplars import select_voice_exemplars


def test_voice_exemplars_are_bounded_deterministic_and_deduped():
    first = select_voice_exemplars(["playful_banter", "close_connection"], limit=3)
    second = select_voice_exemplars(["playful_banter", "close_connection"], limit=3)

    assert first == second
    assert len(first) == 3
    assert len({item["text"] for item in first}) == len(first)
    assert all(set(item) == {"pattern", "text"} for item in first)


def test_voice_exemplars_do_not_invent_unknown_pattern_content():
    assert select_voice_exemplars(["not_a_mary_pattern"], limit=3) == []


def test_banter_exemplars_carry_authored_cadence_not_generic_persona_adjectives():
    values = select_voice_exemplars(["playful_banter"], limit=3)
    text = " ".join(item["text"] for item in values)

    assert "Fantastic observation." in text
    assert "Image rights." in text
    assert "witty" not in text.lower()
    assert "sarcastic" not in text.lower()
