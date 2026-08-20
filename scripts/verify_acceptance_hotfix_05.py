"""Verify V2 acceptance provenance against isolated temporary state."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse
from mary.cognition.reflection import PROVENANCE_AUDIT_VERSION
import mary.cognition.reflection as reflection_module


class SequenceRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=self.responses.pop(0),
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None): return "test"
    def model_name(self, provider=None): return "fake"
    def is_available(self, provider=None): return True
    def routing_strategy(self): return "configured"
    def _provider_order(self, requested=None, route=None): return ["test"]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 ACCEPTANCE HOTFIX 05")
    print("=" * 72)
    print(f"Reflection module: {Path(reflection_module.__file__).resolve()}")
    print(f"Provenance audit version: {PROVENANCE_AUDIT_VERSION}")

    check(
        "Python imported the Hotfix 05 provenance audit",
        PROVENANCE_AUDIT_VERSION == "v2-acceptance-hotfix-05",
    )

    # Critical: Mary() still has legacy relative-path relationship/agency stores.
    # Acceptance verification must never read or mutate the creator's real state.
    original_cwd = Path.cwd()
    with TemporaryDirectory(prefix="maryv2-acceptance-") as temp_dir:
        temp_root = Path(temp_dir).resolve()
        os.chdir(temp_root)
        try:
            router = SequenceRouter([
                "A red panda under a streetlamp could be a cute little sketch idea.",
                "You've been humming that rainy-night red panda idea all along.",
                "That red-panda bit came from my own earlier riff, not from something you told me. I shouldn't turn it into your history.",
            ])
            mary = Mary()
            mary.llm = router
            mary.reasoning.llm = router
            mary.reflection.llm = router

            mary.process("not much just want to have a conversation with you.")
            result = mary.process("Why do you think that?")

            if result.reflection.decision.value != "revise":
                print(f"DEBUG reflection decision: {result.reflection.decision.value}")
                print(f"DEBUG reflection issues: {result.reflection.issues}")
                print(f"DEBUG final response: {result.final_response}")

            check("verifier runs against isolated temporary state", temp_root != original_cwd)
            check("assistant-only creator attribution is revised", result.reflection.decision.value == "revise")
            check("revision identifies Mary's own earlier riff", "came from my own earlier riff" in result.final_response.lower())
            check("false creator attribution is removed", "you've been humming" not in result.final_response.lower())
            check("no web request was created", mary.tools.pending_requests() == [])
        finally:
            os.chdir(original_cwd)

    # Direct overlap regression: even if creator state legitimately contains one
    # overlapping detail, unsupported generated history must not be attributed.
    from mary.cognition.context import CognitiveContext
    from mary.cognition.reasoning import ReasoningResult

    mary = Mary()
    context = CognitiveContext(input_text="Why do you think that?")
    context.user_context = {"interests": {"animal": "red panda"}}
    context.conversation.extend([
        {"role": "user", "content": "not much just want to have a conversation with you."},
        {"role": "assistant", "content": "A red panda under a streetlamp could be a cute little sketch idea."},
    ])
    issues = mary.reflection._conversation_provenance_audit(
        context=context,
        reasoning=ReasoningResult(
            response="You've been humming that rainy-night red panda idea all along."
        ),
    )
    check(
        "partial creator-profile overlap cannot launder unsupported history",
        any(str(issue).startswith("Conversation provenance boundary:") for issue in issues),
    )

    print("=" * 72)
    print("ACCEPTANCE HOTFIX 05 VERIFIED")


if __name__ == "__main__":
    main()
