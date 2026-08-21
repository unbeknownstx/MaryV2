"""Verify that the MaryV2 provider-resilience update is actually installed.

This script is intentionally local-only. It does not call Groq, Tavily, or any
other network provider. It installs a fake rate-limited provider into Mary's
existing LLM router and checks the behaviors that the resilience update adds.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class Fake429Error(Exception):
    status_code = 429


class RateLimitedProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        raise Fake429Error(
            "Error code: 429 - rate limit reached on tokens per day (TPD)"
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "rate-limited-test-model"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("=" * 72)
    print("MARYV2 RESILIENCE INSTALL VERIFICATION")
    print("=" * 72)

    mary = Mary()
    provider = RateLimitedProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    # This verifier is intentionally deterministic/offline. Do not let
    # developer .env fallbacks escape the simulated 429 provider.
    mary.config.llm.fallback_providers = []

    print("Mary core:", Path(__import__("mary.core.mary", fromlist=["x"]).__file__).resolve())
    print("LLM router:", Path(__import__("mary.llm.router", fromlist=["x"]).__file__).resolve())

    with tempfile.TemporaryDirectory(prefix="maryv2-resilience-") as tmp:
        tmp_path = Path(tmp)
        app = create_application(
            mary=mary,
            memory_path=tmp_path / "memory" / "memory.json",
        )

        stored = app.run(
            "want to know something about me remember this : "
            "existence is always precious"
        )
        require(stored.success, "Natural explicit memory store failed.")
        require(
            provider.calls == 0,
            "Memory store incorrectly called the LLM provider.",
        )
        require(
            mary.memory.episodic.all()[-1].content == "existence is always precious",
            "Natural remember-this payload was not extracted correctly.",
        )
        print("PASS natural remember-this storage uses 0 LLM calls")

        recalled = app.run("what do you remember about existence?")
        require(recalled.success, "Memory recall failed.")
        require(provider.calls == 0, "Memory recall incorrectly called the LLM provider.")
        require(
            "existence is always precious" in str(recalled.output).lower(),
            "Memory recall did not return the stored memory.",
        )
        print("PASS deterministic memory recall uses 0 LLM calls")

        conversational = app.run(
            "i will always let you know about my deepest thoughts"
        )
        require(conversational.success, "Rate-limit fallback failed.")
        require(provider.calls == 1, "Expected exactly one conversational LLM attempt.")
        lowered = str(conversational.output).lower()
        require(
            "still here" in lowered and "language engines" in lowered,
            "In-character rate-limit fallback message was not returned.",
        )
        print("PASS ordinary conversation stays in-character on simulated 429")

    print("=" * 72)
    print("RESILIENCE UPDATE INSTALLED CORRECTLY")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
