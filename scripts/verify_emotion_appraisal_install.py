"""Verify Conversation Emotion Appraisal V2 is installed and locally wired."""

from mary.cognition.intent import Intent, IntentType
from mary.expression.emotion import Emotion
from mary.runtime.application import create_application


def main() -> int:
    print("MARYV2 CONVERSATION-EMOTION APPRAISAL VERIFICATION")
    print("=" * 72)

    app = create_application(
        auto_save=False, load_memory=False, load_developed_self=False,
        load_preference_promotion=False, load_knowledge=False,
    )
    mary = app.mary
    checks: list[tuple[str, bool]] = []

    frustration = mary.emotion_appraiser.appraise(
        input_text="I'm frustrated because this keeps breaking.",
        response_text="Let's isolate what's failing.",
        intent=Intent(IntentType.CONVERSATION),
    )
    checks.append((
        "creator frustration maps to Mary's concern rather than copied frustration",
        frustration.emotion == Emotion.CONCERN
        and frustration.creator_emotion == "frustration",
    ))

    achievement = mary.emotion_appraiser.appraise(
        input_text="I finally finished it and all the tests passed.",
        response_text="That's a real milestone.",
        intent=Intent(IntentType.CONVERSATION),
    )
    checks.append((
        "creator achievement produces a pride appraisal",
        achievement.emotion == Emotion.PRIDE,
    ))

    curiosity = mary.emotion_appraiser.appraise(
        input_text="learn this about me: I love creating stories",
        response_text="Got it.",
        intent=Intent(IntentType.RELATIONSHIP_SHARE),
    )
    mary.emotion_appraiser.apply(mary.emotion, curiosity)
    checks.append((
        "meaningful low-intensity appraisal can leave neutral rest state",
        mary.emotion.state.primary == Emotion.CURIOSITY,
    ))

    checks.append((
        "avatar and emotion appraiser share Mary's authoritative emotion manager",
        mary.avatar.emotion_manager is mary.emotion,
    ))

    checks.append((
        "emotion appraisal is deterministic and adds no second LLM dependency",
        not hasattr(mary.emotion_appraiser, "llm"),
    ))

    try:
        failed = False
        for label, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'}  {label}")
            failed = failed or not ok

        print("=" * 72)
        if failed:
            print("CONVERSATION-EMOTION APPRAISAL VERIFICATION FAILED")
            return 1
        print("CONVERSATION-EMOTION APPRAISAL INSTALLED CORRECTLY")
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
