from __future__ import annotations

from mary.core.mary import Mary

from mary.cognition.performance import PerformanceDirector


def test_performance_director_makes_relational_reaction_actable():
    plan = PerformanceDirector().plan(
        disposition={
            "mode": "relational_conversation",
            "expressiveness": 0.92,
            "playfulness": 0.78,
            "warmth": 0.84,
            "familiarity": "familiar",
        },
        emotion={"primary": "pride", "intensity": 0.7},
        continuity={"drive": "react", "allow_follow_up_question": False},
    )

    assert plan.energy > 0.7
    assert plan.spontaneity > 0.6
    assert plan.opening_style == "immediate_reaction"
    assert plan.ending_style == "clean_statement"
    assert plan.allow_fragments is True
    assert any("spoken character dialogue" in note for note in plan.notes)


def test_performance_director_softens_concern_without_flattening_identity():
    plan = PerformanceDirector().plan(
        disposition={
            "mode": "relational_conversation",
            "expressiveness": 0.9,
            "playfulness": 0.7,
            "warmth": 0.85,
            "familiarity": "familiar",
        },
        emotion={"primary": "concern", "intensity": 0.8},
        continuity={"drive": "reflect", "allow_follow_up_question": True},
    )

    assert plan.intimacy >= 0.7
    assert plan.energy > 0.3
    assert plan.pacing in {"soft_deliberate", "natural_conversational"}


def test_turn_mind_exposes_performance_director():
    mary = Mary()
    intent = mary.cognition.detect_intent("I finally got it working.")
    mind = mary.turn_mind.build(
        input_text="I finally got it working.",
        intent=intent,
        recent_conversation=[],
        relevant_memories=[],
    )

    payload = mind.prompt_view()
    assert "performance" in payload
    assert payload["performance"]["opening_style"] == "immediate_reaction"
    assert mary.performance is mary.turn_mind.performance
