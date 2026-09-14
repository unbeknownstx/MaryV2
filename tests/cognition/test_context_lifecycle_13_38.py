from mary.cognition.context_lifecycle import ConversationContextLifecycle


def test_older_user_anchor_keeps_trailing_constraint_when_clipped():
    lifecycle = ConversationContextLifecycle(
        max_turns=1,
        max_characters=600,
        max_message_characters=240,
        max_anchors=1,
        anchor_characters=96,
    )
    older = (
        "Build the feature using the existing architecture. "
        + ("Keep this explanation detailed. " * 10)
        + "BUT NEVER let a worker own Mary's identity or memory."
    )
    history = [
        {"role": "user", "content": older},
        {"role": "assistant", "content": "Understood."},
        {"role": "user", "content": "Now continue."},
        {"role": "assistant", "content": "Continuing."},
    ]

    window = lifecycle.select(history)
    assert len(window.anchors) == 1
    anchor = window.anchors[0]
    assert anchor.startswith("Build the feature")
    assert "identity or memory" in anchor
    assert "older user turn clipped" in anchor
    assert len(anchor) <= 96
    assert window.to_dict()["anchor_policy"] == "user_authored_head_tail_projection"


def test_recent_long_message_uses_same_head_tail_constraint_preservation():
    lifecycle = ConversationContextLifecycle(
        max_turns=1,
        max_characters=800,
        max_message_characters=220,
        max_anchors=0,
        anchor_characters=80,
    )
    recent = "Start important request. " + ("middle " * 100) + "DO NOT AUTO-PROMOTE ANY MODEL."
    window = lifecycle.select([
        {"role": "user", "content": recent},
        {"role": "assistant", "content": "Okay."},
    ])
    text = window.messages[0]["content"]
    assert text.startswith("Start important request")
    assert "DO NOT AUTO-PROMOTE ANY MODEL" in text
    assert len(text) <= 220
