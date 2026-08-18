from __future__ import annotations

from mary.voice import SpeechRenderer


def test_learning_ack_speaks_naturally_without_losing_gui_truth() -> None:
    renderer = SpeechRenderer()
    canonical = (
        "Got it. I've preserved that in memory and added it to my structured "
        "understanding of Unbe as explicit statement."
    )
    spoken = renderer.render(
        canonical,
        user_text="learn this about me: I really love creating stories",
    )

    assert spoken == "Got it. I'll remember that — you really love creating stories."
    assert "structured understanding" not in spoken
    assert canonical.startswith("Got it. I've preserved")


def test_priority_system_response_has_conversational_spoken_form() -> None:
    spoken = SpeechRenderer().render(
        "My current highest-ranked internal priority is Learn more about Unbe (score 1.00)."
    )
    assert spoken == "Right now? Learning more about you."


def test_creator_gap_query_drops_backend_policy_language_for_speech() -> None:
    canonical = (
        "Based on what Unbe has explicitly shared with me, I'm still curious about: "
        "which values Unbe considers most important; how Unbe prefers Mary to communicate with him. "
        "I already have explicit information in these tracked areas: preferences, interests. "
        "These are internal knowledge gaps, not permission for me to interrogate you."
    )
    spoken = SpeechRenderer().render(canonical)

    assert spoken.startswith("I'm still curious about")
    assert "internal knowledge gaps" not in spoken
    assert "Unbe" not in spoken


def test_structured_profile_is_spoken_as_conversation_not_database_dump() -> None:
    canonical = (
        "My current structured understanding of Unbe is based on information he explicitly shared with me. "
        "preferences: favorite color = green | interests: creating stories | facts: test animal = a red panda"
    )
    spoken = SpeechRenderer().render(canonical)

    assert spoken.startswith("Here's what I know about you so far.")
    assert "Your favorite color is green." in spoken
    assert "You like creating stories." in spoken
    assert "Your test animal is a red panda." in spoken
    assert "structured understanding" not in spoken
