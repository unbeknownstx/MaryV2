from pathlib import Path

from mary.cognition.continuity import ConversationContinuity, ConversationalDrive
from mary.cognition.intent import IntentType
from mary.conversation.lanes import ConversationLane
from mary.conversation.reflection_policy import (
    choose_reflection_action,
    local_conversation_repair,
)
from mary.development.preference_evidence import extract_preference_evidence_items


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_what_are_you_on_about_is_a_repair_turn_not_fresh_banter():
    snapshot = ConversationContinuity().build(
        input_text="what is u on about",
        intent_type=IntentType.CONVERSATION,
        recent_conversation=[
            {
                "role": "assistant",
                "content": "What's the vibe? Hit me with the deets.",
            }
        ],
    )

    assert snapshot.drive == ConversationalDrive.REFLECT


def test_creator_can_naturally_ask_mary_to_be_less_hard():
    evidence = extract_preference_evidence_items("i hate how hard you are")

    directness = [item for item in evidence if item.signal == "directness"]
    assert len(directness) == 1
    assert directness[0].polarity < 0
    assert directness[0].evidence_class == "corrective_feedback"


def test_stacked_slang_can_be_repaired_without_second_model_call():
    issue = (
        "Conversation register boundary: over-forces rare slang/register "
        "instead of matching the current turn."
    )
    decision = choose_reflection_action(
        ConversationLane.CONVERSATION,
        [issue],
    )
    assert decision.action == "local_repair"

    repaired = local_conversation_repair(
        "Nah fam, I'm just here to work with you — no drama, no fluff. "
        "Let's get that beat cooked."
    )
    lowered = repaired.lower()
    assert "nah fam" not in lowered
    assert "no drama" not in lowered
    assert "beat cooked" not in lowered
    assert "i'm just here to work with you" in lowered
    assert "let's get it done" in lowered

    softened = local_conversation_repair(
        "I'm soft at heart, bucko. You're just getting the direct version today."
    )
    assert softened == (
        "I'm soft at heart. You're just getting the direct version today."
    )


def test_ordinary_model_projection_does_not_dump_rare_slang_tokens():
    mind = _text("mary/cognition/mind_state.py")
    reasoning = _text("mary/cognition/reasoning.py")
    character = _text("mary/personality/character_core.py")

    assert "Mary's available casual slang includes" not in mind
    assert "Distinctive slang and teasing nicknames are rare vocabulary evidence" in mind
    assert '"vocabulary": list(speech.get("vocabulary", []) or [])[:3]' not in reasoning
    assert '"rare_vocabulary_policy"' in reasoning
    assert "rare vocabulary evidence, not signature tokens" in character
