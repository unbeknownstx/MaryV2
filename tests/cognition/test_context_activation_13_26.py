from __future__ import annotations

from mary.cognition.context_activation import ContextActivationEngine, ContextCue


def _engine(**kwargs) -> ContextActivationEngine:
    return ContextActivationEngine(
        [
            ContextCue(
                cue_id="blue-room",
                keys=("blue room", "studio*"),
                text="The blue room is the current streaming set.",
                source="creator_project_notes",
                priority=5,
            ),
            ContextCue(
                cue_id="meeting-scene",
                keys=("meeting scene",),
                text="Use the approved meeting-scene timing and do not invent un-scripted beats.",
                source="project_direction",
                priority=10,
            ),
        ],
        **kwargs,
    )


def test_only_recent_messages_trigger_context() -> None:
    engine = _engine(recent_messages=2)
    history = [
        {"role": "user", "content": "meeting scene"},
        {"role": "assistant", "content": "old reply"},
        {"role": "user", "content": "something else"},
    ]
    assert engine.activate(history) == ()


def test_activation_is_bounded_and_provenanced() -> None:
    engine = _engine(max_characters=300)
    view = engine.prompt_view([{"role": "user", "content": "Let's work on the meeting scene."}])
    assert len(view["items"]) == 1
    assert view["items"][0]["id"] == "meeting-scene"
    assert view["items"][0]["source"] == "project_direction"
    assert view["items"][0]["boundary"] == "ephemeral_context_not_memory"
    assert view["persistence"] == "none"


def test_priority_controls_budget_selection() -> None:
    engine = _engine(max_characters=128, max_activations=1)
    active = engine.activate([
        {"role": "user", "content": "The blue room meeting scene studio plan."}
    ])
    assert len(active) == 1
    assert active[0].cue_id == "meeting-scene"


def test_wildcards_are_narrow_and_deterministic() -> None:
    engine = _engine()
    active = engine.activate([{"content": "studio setup for tonight"}])
    assert [item.cue_id for item in active] == ["blue-room"]


def test_activated_text_does_not_recursively_trigger_other_cues() -> None:
    engine = ContextActivationEngine([
        ContextCue(cue_id="one", keys=("alpha",), text="beta secret context"),
        ContextCue(cue_id="two", keys=("beta",), text="must not activate recursively"),
    ])
    active = engine.activate([{"content": "alpha"}])
    assert [item.cue_id for item in active] == ["one"]


def test_oversized_item_is_not_partially_injected() -> None:
    engine = ContextActivationEngine(
        [ContextCue(cue_id="huge", keys=("hello",), text="x" * 500)],
        max_characters=128,
    )
    assert engine.activate([{"content": "hello"}]) == ()
