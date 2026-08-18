"""Verify MaryV2 Performance Pass V1 without external provider calls."""

from __future__ import annotations

from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
    LLMRateLimitError,
)
from mary.llm.router import LLMRouter


class SequenceRouter:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            return LLMResponse(
                content="Mm, no—I actually disagree. The architecture isn't the problem; we just haven't learned how to use all of me together yet.",
                provider="verify",
                model="fake",
            )
        content = self.responses.pop(0) if self.responses else "Yeah. I'm here."
        return LLMResponse(content=content, provider="verify", model="fake")

    def provider_name(self, provider=None):
        return "verify"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


class FailingProvider(LLMInterface):
    def generate(self, messages, temperature=0.7, max_tokens=2048):
        raise LLMRateLimitError("quota reached", provider="primary")

    def is_available(self):
        return True

    def provider_name(self):
        return "primary"

    def model_name(self):
        return "primary-model"


class GoodProvider(LLMInterface):
    def generate(self, messages, temperature=0.7, max_tokens=2048):
        return LLMResponse(
            content="Still here.",
            provider="secondary",
            model="secondary-model",
        )

    def is_available(self):
        return True

    def provider_name(self):
        return "secondary"

    def model_name(self):
        return "secondary-model"


def _wire(mary: Mary, router) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router


def _pass(label: str) -> None:
    print(f"PASS  {label}")


def main() -> int:
    print("MARYV2 PERFORMANCE PASS V1 VERIFICATION")
    print("=" * 72)

    router = SequenceRouter(["Okay. That's a solid milestone. What's on your radar next?"])
    mary = Mary()
    _wire(mary, router)
    result = mary.process("I finally got everything working and all the tests passed.")

    mind = result.context.mind_state
    performance = mind.get("performance", {})
    if not performance or performance.get("opening_style") != "immediate_reaction":
        raise AssertionError("Performance Director is not shaping the turn")
    _pass("TurnMindState carries a real acting/performance plan")

    first_prompt = router.calls[0][0]
    if "performing Mary Cosma's dialogue" not in first_prompt[0].content:
        raise AssertionError("reasoning system prompt is not performance-first")
    if "Performance Director" not in first_prompt[1].content:
        raise AssertionError("performance plan is not supplied to reasoning")
    _pass("reasoning asks the model to perform Mary, not write support copy")

    if "?" in result.final_response or "radar" in result.final_response.lower():
        raise AssertionError("polished assistant closer was not revised away")
    _pass("assistant-shaped cadence/questions are audited and revised")

    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    failover = LLMRouter(config)
    failover.register_provider("primary", FailingProvider())
    failover.register_provider("secondary", GoodProvider())
    response = failover.generate([LLMMessage(role="user", content="hello")])
    if response.provider != "secondary":
        raise AssertionError("router did not fail over after rate limit")
    _pass("rate-limited provider fails over to the next explicitly configured provider")

    config2 = Config.from_environment()
    if not isinstance(config2.llm.fallback_providers, list):
        raise AssertionError("fallback provider configuration is not available")
    _pass("provider fallback order is environment-configurable and opt-in")

    fallback_text = mary.reasoning._character_provider_fallback(
        context=result.context,
        rate_limited=True,
    )
    if "still here" not in fallback_text.lower() or "language engines" not in fallback_text.lower():
        raise AssertionError("local provider failure response is not characterful")
    _pass("when all language engines fail, Mary stays in-character instead of dumping a canned error")

    print("=" * 72)
    print("MARYV2 PERFORMANCE PASS V1 INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
