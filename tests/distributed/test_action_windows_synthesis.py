import pytest

from mary.distributed.action_windows import ActionSpec, ActionWindowRegistry


def test_action_window_exposes_only_current_valid_actions_and_disposes_one_shot_action():
    registry = ActionWindowRegistry(max_windows=8)
    window = registry.open(
        surface="game",
        context="dialog choice",
        actions=(
            ActionSpec(name="choose_left", description="Choose the left response", schema={"type": "object", "properties": {}, "additionalProperties": False}, disposable=True),
            ActionSpec(name="inspect", description="Inspect current state", schema={"type": "object", "properties": {}, "additionalProperties": False}),
        ),
    )
    selected = registry.select(window_id=window.window_id, action="choose_left", args={}, expected_revision=window.revision)
    assert selected.action == "choose_left"
    current = registry.get(window.window_id)
    assert current is not None
    assert list(current.actions) == ["inspect"]
    with pytest.raises(LookupError):
        registry.select(window_id=current.window_id, action="choose_left", args={}, expected_revision=current.revision)


def test_action_window_rejects_stale_revision_and_invalid_arguments():
    registry = ActionWindowRegistry()
    window = registry.open(
        surface="world",
        context="near desk",
        actions=(ActionSpec(name="look_at", description="Look at target", schema={"type": "object", "required": ["target"], "properties": {"target": {"type": "string"}}, "additionalProperties": False}),),
    )
    with pytest.raises(ValueError):
        registry.select(window_id=window.window_id, action="look_at", args={}, expected_revision=window.revision)
    revised = registry.open(surface="world", context="near desk", actions=tuple(window.actions.values()), window_id=window.window_id)
    with pytest.raises(RuntimeError):
        registry.select(window_id=revised.window_id, action="look_at", args={"target": "desk"}, expected_revision=window.revision)
