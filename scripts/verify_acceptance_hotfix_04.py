"""Verify the V2 acceptance provenance hotfix is the code Python is importing."""
from __future__ import annotations

from pathlib import Path

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import IntentType
from mary.cognition.reasoning import ReasoningResult
from mary.cognition.reflection import PROVENANCE_AUDIT_VERSION, ReflectionEngine
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse
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
    print("MARY V2 ACCEPTANCE HOTFIX 04")
    print("=" * 72)
    print(f"Reflection module: {Path(reflection_module.__file__).resolve()}")
    print(f"Provenance audit version: {PROVENANCE_AUDIT_VERSION}")

    check(
        "Python imported the Hotfix 04 provenance audit",
        PROVENANCE_AUDIT_VERSION == "v2-acceptance-hotfix-04",
    )

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

    check("assistant-only creator attribution is revised", result.reflection.decision.value == "revise")
    check("revision identifies Mary's own earlier riff", "came from my own earlier riff" in result.final_response.lower())
    check("false creator attribution is removed", "you've been humming" not in result.final_response.lower())
    check("no web request was created", mary.tools.pending_requests() == [])

    print("=" * 72)
    print("ACCEPTANCE HOTFIX 04 VERIFIED")


if __name__ == "__main__":
    main()
