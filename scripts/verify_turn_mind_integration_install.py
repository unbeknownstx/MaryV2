"""Verify the MaryV2 unified TurnMindState integration without external calls."""

from __future__ import annotations

import os
from tempfile import TemporaryDirectory

from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application


class FakeRouter:
    def __init__(self, response: str = "Hey. I'm here.") -> None:
        self.response = response
        self.calls: list[tuple[object, dict]] = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            return LLMResponse(
                content="Finally. That one fought us way harder than it should have.",
                provider="verify",
                model="fake",
            )
        return LLMResponse(
            content=self.response,
            provider="verify",
            model="fake",
        )

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


def _pass(label: str) -> None:
    print(f"PASS  {label}")


def main() -> int:
    print("MARYV2 TURN-MIND INTEGRATION VERIFICATION")
    print("=" * 72)

    original = os.getcwd()
    previous_local_mind = os.environ.get("MARY_LOCAL_MIND_ENABLED")
    with TemporaryDirectory(prefix="maryv2_turnmind_", ignore_cleanup_errors=True) as temp:
        try:
            os.chdir(temp)
            # This milestone specifically verifies the full TurnMind -> reasoning
            # -> reflection path. 12.12 adds a pre-cognition local reflex layer,
            # so disable that optional front porch for this historical verifier.
            os.environ["MARY_LOCAL_MIND_ENABLED"] = "false"

            router = FakeRouter()
            app = create_application()
            mary = app.mary
            _wire(mary, router)

            first = app.run("Hello Mary").metadata["pipeline_values"]["cognitive_cycle"]
            mind = first.context.mind_state
            required = {
                "identity", "biography", "personality", "character", "values",
                "relationship", "memory", "knowledge", "learning", "agency",
                "autonomy", "tools", "emotion", "conversation", "disposition",
                "performance", "constraints",
            }
            if not required.issubset(mind):
                raise AssertionError(f"TurnMindState missing: {sorted(required - set(mind))}")
            _pass("identity, biography, character, relationship, memory, knowledge, learning, agency, autonomy, tools, emotion and disposition share one turn state")

            if len(router.calls) != 1:
                raise AssertionError("natural response spent an unnecessary reflection LLM call")
            _pass("natural Mary response uses one LLM call; reflection is local")

            second = app.run("That was interesting.").metadata["pipeline_values"]["cognitive_cycle"]
            history = second.context.conversation
            if not any(item.get("role") == "user" and item.get("content") == "Hello Mary" for item in history):
                raise AssertionError("previous creator turn was not fed into cognition")
            if not any(item.get("role") == "assistant" and item.get("content") == "Hey. I'm here." for item in history):
                raise AssertionError("previous Mary response was not fed into cognition")
            _pass("completed dialogue becomes real context for the next turn")

            prompt_messages = router.calls[0][0]
            if "You are Mary" not in prompt_messages[0].content:
                raise AssertionError("reasoning system prompt is not character-first")
            if "TurnMindState" not in prompt_messages[1].content:
                raise AssertionError("integrated state is not supplied to reasoning")
            _pass("reasoning is character-first and receives TurnMindState")

            generic = FakeRouter(
                "Great to hear that! Anything else you'd like to tackle next?"
            )
            app2 = create_application()
            mary2 = app2.mary
            _wire(mary2, generic)
            revised = app2.run(
                "I finally got it working and all the tests passed."
            ).metadata["pipeline_values"]["cognitive_cycle"]
            if revised.final_response != "Finally. That one fought us way harder than it should have.":
                raise AssertionError("generic assistant response was not actually revised")
            if len(generic.calls) != 2:
                raise AssertionError("targeted character revision should use exactly one additional call")
            _pass("generic assistant-shaped replies are detected, revised, and the revision is actually used")

            if not first.metadata.get("dialogue_recorded"):
                raise AssertionError("completed turn was not committed to DialogueManager")
            _pass("normal Mary turns are committed through the existing dialogue/expression systems")

        finally:
            if 'app2' in locals():
                app2.close()
            if 'app' in locals():
                app.close()
            if previous_local_mind is None:
                os.environ.pop("MARY_LOCAL_MIND_ENABLED", None)
            else:
                os.environ["MARY_LOCAL_MIND_ENABLED"] = previous_local_mind
            os.chdir(original)

    print("=" * 72)
    print("TURN-MIND INTEGRATION INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
