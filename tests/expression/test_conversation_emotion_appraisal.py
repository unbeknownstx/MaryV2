from __future__ import annotations

from mary.cognition.intent import Intent, IntentType
from mary.expression.appraisal import ConversationEmotionAppraiser
from mary.expression.emotion import Emotion, EmotionManager, EmotionalState


def test_creator_frustration_becomes_mary_concern_not_copied_frustration() -> None:
    appraiser = ConversationEmotionAppraiser()
    appraisal = appraiser.appraise(
        input_text="I'm frustrated because this keeps breaking.",
        response_text="I can see why that's frustrating. Let's isolate it.",
        intent=Intent(IntentType.CONVERSATION),
    )

    assert appraisal.creator_emotion == "frustration"
    assert appraisal.emotion == Emotion.CONCERN
    assert appraisal.intensity >= 0.6


def test_creator_achievement_becomes_pride() -> None:
    appraiser = ConversationEmotionAppraiser()
    appraisal = appraiser.appraise(
        input_text="I finally finished MaryV2 and all the tests passed.",
        response_text="That's a real milestone.",
        intent=Intent(IntentType.CONVERSATION),
    )

    assert appraisal.emotion == Emotion.PRIDE
    assert appraisal.creator_emotion == "positive_achievement"


def test_relationship_share_creates_low_intensity_curiosity() -> None:
    appraiser = ConversationEmotionAppraiser()
    appraisal = appraiser.appraise(
        input_text="learn this about me: I love old science fiction",
        response_text="Got it.",
        intent=Intent(IntentType.RELATIONSHIP_SHARE),
    )

    assert appraisal.emotion == Emotion.CURIOSITY
    assert 0.25 <= appraisal.intensity < 0.6


def test_marys_existing_reasoning_can_supply_explicit_emotional_expression() -> None:
    appraiser = ConversationEmotionAppraiser()
    appraisal = appraiser.appraise(
        input_text="What do you think?",
        response_text="I'm curious where you want to take that next.",
        intent=Intent(IntentType.QUESTION),
    )

    assert appraisal.emotion == Emotion.CURIOSITY
    assert appraisal.source == "mary_response_expression"


def test_apply_promotes_meaningful_signal_from_neutral_and_decays_previous_state() -> None:
    manager = EmotionManager(
        EmotionalState(primary=Emotion.NEUTRAL, intensity=0.0, updated_at=100.0)
    )
    appraiser = ConversationEmotionAppraiser()
    appraisal = appraiser.appraise(
        input_text="learn this about me: I love creating stories",
        response_text="Got it.",
        intent=Intent(IntentType.RELATIONSHIP_SHARE),
    )

    state = appraiser.apply(manager, appraisal, now=101.0)

    assert state.primary == Emotion.CURIOSITY
    assert state.intensity > 0.25
    assert state.metadata["last_conversation_appraisal"]["emotion"] == "curiosity"


def test_no_signal_decays_toward_neutral_instead_of_switching_randomly() -> None:
    manager = EmotionManager(
        EmotionalState(
            primary=Emotion.EXCITEMENT,
            intensity=0.55,
            valence=0.7,
            arousal=0.8,
            updated_at=100.0,
        )
    )
    appraiser = ConversationEmotionAppraiser()
    appraisal = appraiser.appraise(
        input_text="Please explain the next command.",
        response_text="Run the verifier and paste the output.",
        intent=Intent(IntentType.REQUEST),
    )

    state = appraiser.apply(manager, appraisal, now=101.0)

    assert appraisal.emotion == Emotion.NEUTRAL
    assert state.primary == Emotion.EXCITEMENT
    assert 0.0 < state.intensity < 0.55
    assert state.valence < 0.7
    assert state.arousal < 0.8
