from mary.mind.behavior import CharacterBehaviorAction, CharacterBehaviorEngine


def test_focus_idle_is_nonverbal():
    engine = CharacterBehaviorEngine(seed=1)
    result = engine.idle_decision(
        focus_active=True,
        pending_thoughts=[],
        idle_action={"kind": "animation", "name": "look_side"},
    )
    assert result.action == CharacterBehaviorAction.IDLE_ANIMATION
    assert result.payload["focus_quiet"] is True


def test_pending_thought_is_not_turned_into_spoken_text():
    engine = CharacterBehaviorEngine(seed=2)
    result = engine.idle_decision(
        focus_active=False,
        pending_thoughts=[{"id": "t1", "text": "grounded observation", "importance": .95, "source": "presence"}],
        idle_action={"kind": "animation", "name": "head_tilt"},
    )
    assert "grounded observation" not in str(result.to_dict())
