from __future__ import annotations

from mary.core.mary import Mary
from mary.runtime.live_state import format_character_card


def test_live_state_is_compact_display_state_not_raw_memory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary.memory.remember_event("VERY_PRIVATE_MEMORY_BODY")
    state = mary.live_state()
    rendered = str(state)

    assert state["character"]["name"] == "Mary"
    assert state["character"]["memory_count"] >= 1
    assert "VERY_PRIVATE_MEMORY_BODY" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "paid_expert" in state["privacy"]


def test_character_card_surfaces_state_without_claiming_human_emotion(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    card = format_character_card(mary.live_state(runtime_status="listening"))
    assert "MY CHARACTERS" in card
    assert "Mary" in card
    assert "Status:       Listening" in card
    assert "Mood:" in card
