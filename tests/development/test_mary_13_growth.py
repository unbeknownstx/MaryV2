from pathlib import Path

from mary.conversation.engagement import ConversationEngagement
from mary.runtime.application import create_application


def test_intentional_conversation_opens_persistent_thread(tmp_path):
    e = ConversationEngagement()
    e.configure(tmp_path / "engagement.json")
    plan = e.begin_turn("go ahead and ask me some questions and get to know me")
    assert plan.effective_mode == "engaged"
    assert plan.allow_follow_up_question is True
    assert plan.turns_remaining == 8
    e.complete_turn("What do you care about most?")
    fresh = ConversationEngagement()
    fresh.configure(tmp_path / "engagement.json")
    assert fresh.status()["active_session"]["mode"] == "engaged"
    assert fresh.status()["active_session"]["turns_remaining"] == 7


def test_explicit_learning_invitation_uses_real_gap_and_records_experience(tmp_path):
    app = create_application(
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed.json",
        preference_promotion_path=tmp_path / "personality" / "promotion.json",
    )
    result = app.mary.process("go ahead and ask me some questions get to know me")
    assert "?" in result.final_response
    assert "language engines" not in result.final_response.lower()
    assert app.mary.engagement.status()["active_session"]["mode"] == "engaged"
    assert app.mary.growth.status()["journal"]["records"] == 1
    assert app.mary.growth.status()["policy"]["model_dialogue_counts_as_self_evidence"] is False


def test_growth_auto_promotion_is_stricter_than_candidate_eligibility(tmp_path):
    app = create_application(
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed.json",
        preference_promotion_path=tmp_path / "personality" / "promotion.json",
    )
    mary = app.mary
    for i in range(3):
        mary.observe_preference_experience(
            "night drives", category="activity", strength=.9, confidence=.95,
            source="creator_observed_choice", evidence_id=f"e{i}",
        )
    assert mary.evaluate_preference_candidate("night drives")["eligible"] is True
    assert mary.growth._promote_strict_preference_candidates() == []
    assert mary.preferences.get_preference("night drives") is None
    for i in range(3, 5):
        mary.observe_preference_experience(
            "night drives", category="activity", strength=.9, confidence=.95,
            source="creator_observed_choice", evidence_id=f"e{i}",
        )
    assert mary.growth._promote_strict_preference_candidates() == ["night drives"]
    assert mary.preferences.get_preference("night drives") is not None


def test_growth_status_separates_process_activity_from_durable_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_application(
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed.json",
        preference_promotion_path=tmp_path / "personality" / "promotion.json",
    )
    mary = app.mary

    mary.memory.remember_fact(
        "creator",
        "favorite_color",
        "blue",
        confidence=1.0,
        source="creator_explicit",
    )
    mary.set_developed_preference(
        "late-night jazz",
        category="music",
        strength=0.9,
        confidence=0.95,
        source="experience_promotion",
    )
    mary.relationship_milestones.add_milestone(
        title="A durable checkpoint",
        description="A bounded test milestone.",
        category="mary_development",
        importance=0.8,
    )

    status = mary.growth.status()

    assert status["counter_scope"] == "current_core_process"
    assert status["process_counters"] == {
        "semantic_promotions": 0,
        "preference_promotions": 0,
        "milestones_created": 0,
    }
    assert status["durable_state"]["semantic_memories"] == 1
    assert status["durable_state"]["developed_preferences"] == 1
    assert status["durable_state"]["developed_personality_traits"] == 0
    assert status["durable_state"]["relationship_milestones"] == 1
    assert status["policy"]["process_counters_are_durable_totals"] is False
