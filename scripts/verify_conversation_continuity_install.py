"""Verify Conversation Continuity V2 without external provider calls."""

from __future__ import annotations

import os
from tempfile import TemporaryDirectory

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


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


def _wire(mary: Mary, router: FakeRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router


def _pass(label: str) -> None:
    print(f"PASS  {label}")


def main() -> int:
    print("MARYV2 CONVERSATION-CONTINUITY V2 VERIFICATION")
    print("=" * 72)

    original = os.getcwd()
    with TemporaryDirectory(prefix="maryv2_continuity_", ignore_cleanup_errors=True) as temp:
        try:
            os.chdir(temp)

            router = FakeRouter([
                "What part of the build gave you the most satisfaction?",
                "Which parts do you feel are the most over-engineered?",
            ])
            mary = Mary()
            _wire(mary, router)

            mary.process("We've spent all day building you.")
            second = mary.process("I think we might have overengineered some of this.")
            continuity = second.context.mind_state.get("continuity", {})
            if continuity.get("drive") != "opine":
                raise AssertionError("overengineering turn did not select OPINE drive")
            if continuity.get("allow_follow_up_question") is not False:
                raise AssertionError("question budget did not close after a recent Mary question")
            if "?" in second.final_response:
                raise AssertionError("second consecutive follow-up question was not revised away")
            _pass("conversational drives and question budget shape actual responses")

            disagree = mary.process("You can disagree with me, you know.")
            if disagree.context.mind_state.get("continuity", {}).get("drive") != "disagree":
                raise AssertionError("explicit disagreement invitation did not select DISAGREE")
            _pass("Mary can select disagreement/opinion instead of reflexive follow-up")

            calls_before = len(router.calls)
            recalled = mary.process("What do you remember from what we were just talking about?")
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
            mary2 = Mary()
            _wire(mary2, repeat_router)
            mary2.process("We may have overbuilt this.")
            repeated = mary2.process("Some of it still feels too complicated.")
            if repeated.final_response.lower().startswith("sounds like a classic"):
                raise AssertionError("recent opening repetition was not revised")
            _pass("recent opening/metaphor-pattern repetition is audited and revised")

            if not hasattr(mary, "continuity") or mary.continuity is not mary.turn_mind.continuity:
                raise AssertionError("continuity system is not authoritative/shared")
            _pass("ConversationContinuity is shared through the authoritative TurnMindState")

        finally:
            os.chdir(original)

    print("=" * 72)
    print("CONVERSATION CONTINUITY V2 INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
