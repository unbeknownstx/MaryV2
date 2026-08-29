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

    router = SequenceRouter(["I think that tension matters because systems can become more important than the people they were meant to serve."])
    mary = Mary()
    _wire(mary, router)

    # A bounded shared-work milestone is now a CharacterMind reflex.  This is
    # intentional: the release verifier must not require an LLM call merely to
    # prove that Mary has a performance plan.
    milestone = mary.process("I finally got everything working and all the tests passed.")
    mind = milestone.context.mind_state
    performance = mind.get("performance", {})
    if not performance or performance.get("opening_style") != "immediate_reaction":
        raise AssertionError("Performance Director is not shaping the turn")
    if milestone.metadata.get("llm_calls_after_action") != 0 or milestone.metadata.get("handled_by") != "mary_local_mind":
        raise AssertionError("bounded milestone did not remain a zero-call CharacterMind reflex")
    _pass("TurnMindState shapes a milestone that CharacterMind can express with zero LLM calls")

    # Use a genuinely open-ended turn to verify the provider-facing character
    # and performance contract.  Open conversation still belongs to Mary's
    # language cortex; only already-represented reflexes bypass it.
    result = mary.process(
        "I keep thinking about why people build systems that eventually start controlling them."
    )
    if not router.calls:
        raise AssertionError("open-ended conversation did not escalate to the language cortex")
    first_prompt = router.calls[0][0]
    system_prompt = str(first_prompt[0].content)
    user_prompt = str(first_prompt[1].content)
    natural_performance_policy = (
        ("Sound like Mary is simply talking" in system_prompt and "not performing the role of Mary for an audience" in system_prompt)
        or ("Voice/avatar acting is handled by the performance layer" in system_prompt and "TurnMind-to-dialogue contract" in system_prompt)
    )
    legacy_performance_policy = "performing Mary Cosma's dialogue" in system_prompt
    if not (natural_performance_policy or legacy_performance_policy):
        raise AssertionError("reasoning system prompt has no character-performance policy")
    if (
        ("Performance direction:" not in system_prompt and "Performance=" not in system_prompt)
        or "Compact TurnMindState" not in user_prompt
        or "'performance':" not in user_prompt
    ):
        raise AssertionError("performance plan is not supplied to reasoning")
    _pass("reasoning keeps Mary character-first without stage-performing ordinary dialogue")

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
