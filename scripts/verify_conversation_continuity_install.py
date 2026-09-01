"""Verify Conversation Continuity V2 without external provider calls."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.cognition.intent import IntentType
from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application


class FakeRouter:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            return LLMResponse(
                content="Maybe a little. I think the bigger problem was integration, not the architecture itself.",
                provider="verify",
                model="fake",
            )
        content = self.responses.pop(0) if self.responses else "Yeah. I'm with you."
        return LLMResponse(content=content, provider="verify", model="fake")

    def provider_name(self, provider=None):
        return "verify"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def _wire(mary, router: FakeRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def _pass(label: str) -> None:
    print(f"PASS  {label}")


def main() -> int:
    print("MARYV2 CONVERSATION-CONTINUITY V2 VERIFICATION")
    print("=" * 72)

    original = os.getcwd()
    with TemporaryDirectory(prefix="maryv2_continuity_", ignore_cleanup_errors=True) as temp:
        app = None
        app2 = None
        try:
            os.chdir(temp)

            router = FakeRouter([
                "What part of the build gave you the most satisfaction?",
                "Which parts do you feel are the most over-engineered?",
            ])
            app = create_application(
                memory_path=Path(temp) / "data" / "memory" / "memory.json",
                auto_save=False, load_memory=False, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            mary = app.mary
            _wire(mary, router)

            first = _turn(app, "We've spent all day building you.")
            second = _turn(app, "I think we might have overengineered some of this.")
            continuity = second.context.mind_state.get("continuity", {})
            if continuity.get("drive") != "opine":
                raise AssertionError("overengineering turn did not select OPINE drive")
            if continuity.get("drive") == "ask":
                raise AssertionError("opinion turn incorrectly selected ASK")
            # If the first response still contains a question, the question budget
            # must close. Performance Pass may instead remove that unnecessary
            # question on the first turn, which is an even stronger result.
            if "?" in first.final_response and continuity.get("allow_follow_up_question") is not False:
                raise AssertionError("question budget did not close after a recent Mary question")
            if "?" in second.final_response:
                raise AssertionError("opinion turn still ended with an unnecessary follow-up question")
            _pass("conversational drives and question budget shape actual responses")

            disagree = _turn(app, "You can disagree with me, you know.")
            if disagree.context.mind_state.get("continuity", {}).get("drive") != "disagree":
                raise AssertionError("explicit disagreement invitation did not select DISAGREE")
            _pass("Mary can select disagreement/opinion instead of reflexive follow-up")

            calls_before = len(router.calls)
            recalled = _turn(app, "What do you remember from what we were just talking about?")
            if recalled.intent.intent_type != IntentType.CONVERSATION_RECALL:
                raise AssertionError("recent-dialogue recall was misrouted to long-term memory")
            if len(router.calls) != calls_before:
                raise AssertionError("recent-dialogue recall spent an unnecessary LLM call")
            if "overengineered" not in recalled.final_response.lower() and "disagree" not in recalled.final_response.lower():
                raise AssertionError("recent-dialogue recall did not use actual recent dialogue")
            _pass("recent-dialogue recall wins before persistent memory and uses 0 LLM calls")

            repeat_router = FakeRouter([
                "Sounds like a classic too-many-knobs scenario.",
                "Sounds like a classic feature-fatigue moment.",
            ])
            app2 = create_application(
                memory_path=Path(temp) / "second_data" / "memory" / "memory.json",
                auto_save=False, load_memory=False, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            mary2 = app2.mary
            _wire(mary2, repeat_router)
            _turn(app2, "We may have overbuilt this.")
            repeated = _turn(app2, "Some of it still feels too complicated.")
            if repeated.final_response.lower().startswith("sounds like a classic"):
                raise AssertionError("recent opening repetition was not revised")
            _pass("recent opening/metaphor-pattern repetition is audited and revised")

            if not hasattr(mary, "continuity") or mary.continuity is not mary.turn_mind.continuity:
                raise AssertionError("continuity system is not authoritative/shared")
            _pass("ConversationContinuity is shared through the authoritative TurnMindState")

        finally:
            if app2 is not None:
                app2.close()
            if app is not None:
                app.close()
            os.chdir(original)

    print("=" * 72)
    print("CONVERSATION CONTINUITY V2 INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
