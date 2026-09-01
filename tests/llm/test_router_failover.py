from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
    LLMRateLimitError,
)
from mary.llm.router import LLMRouter


class FailingProvider(LLMInterface):
    def __init__(self, name: str = "primary"):
        self.name = name

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        raise LLMRateLimitError("quota reached", provider=self.name)

    def is_available(self):
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return "failing"


class GoodProvider(LLMInterface):
    def __init__(self, name: str = "secondary"):
        self.name = name

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        return LLMResponse(
            content="Mary is still here.",
            provider=self.name,
            model="good",
        )

    def is_available(self):
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return "good"


def test_router_fails_over_when_primary_rate_limits():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    router = LLMRouter(config)
    router.register_provider("primary", FailingProvider("primary"))
    router.register_provider("secondary", GoodProvider("secondary"))

    response = router.generate([LLMMessage(role="user", content="hello")])

    assert response.content == "Mary is still here."
    assert response.provider == "secondary"
    assert router.last_generation_attempts == [
        {"provider": "primary", "status": "failed", "error": "quota reached"},
        {"provider": "secondary", "status": "success", "error": ""},
    ]


def test_router_skips_unavailable_fallbacks_and_keeps_order():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["missing", "secondary", "secondary"]
    router = LLMRouter(config)
    router.register_provider("primary", FailingProvider("primary"))
    router.register_provider("secondary", GoodProvider("secondary"))

    response = router.generate([LLMMessage(role="user", content="hello")])

    assert response.provider == "secondary"
    assert [item["provider"] for item in router.last_generation_attempts] == [
        "primary",
        "missing",
        "secondary",
    ]


def test_router_cools_down_rate_limited_provider_on_next_turn():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    config.llm.rate_limit_cooldown_seconds = 300

    router = LLMRouter(config)
    router.register_provider("primary", FailingProvider("primary"))
    router.register_provider("secondary", GoodProvider("secondary"))

    first = router.generate([
        LLMMessage(role="user", content="hello"),
    ])
    assert first.provider == "secondary"

    second = router.generate([
        LLMMessage(role="user", content="hello again"),
    ])

    assert second.provider == "secondary"
    assert router.last_generation_attempts[0]["provider"] == "primary"
    assert router.last_generation_attempts[0]["status"] == "cooldown"
    assert router.last_generation_attempts[1] == {
        "provider": "secondary",
        "status": "success",
        "error": "",
    }


def test_clear_provider_cooldown_reenables_provider():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]

    router = LLMRouter(config)
    router.register_provider("primary", FailingProvider("primary"))
    router.register_provider("secondary", GoodProvider("secondary"))

    router.generate([
        LLMMessage(role="user", content="hello"),
    ])

    assert router._cooldown_remaining("primary") > 0

    router.clear_provider_cooldown("primary")

    assert router._cooldown_remaining("primary") == 0


def test_execution_policy_blocks_provider_availability_and_generation_then_allows():
    config = Config()
    config.llm.provider = "primary"
    router = LLMRouter(config)

    class TrackingProvider(GoodProvider):
        def __init__(self):
            super().__init__("primary")
            self.availability_calls = 0
            self.generation_calls = 0

        def is_available(self):
            self.availability_calls += 1
            return True

        def generate(self, messages, temperature=0.7, max_tokens=2048):
            self.generation_calls += 1
            return super().generate(messages, temperature, max_tokens)

    provider = TrackingProvider()
    router.register_provider("primary", provider)

    def deny(kind: str) -> None:
        assert kind == "llm.generate"
        raise RuntimeError("creator surface is unavailable")

    router.set_execution_policy(deny)
    try:
        router.generate([LLMMessage(role="user", content="hello")])
        assert False, "denied generation must raise"
    except RuntimeError as exc:
        assert str(exc) == "creator surface is unavailable"

    assert provider.availability_calls == 0
    assert provider.generation_calls == 0

    router.set_execution_policy(None)
    response = router.generate([LLMMessage(role="user", content="hello")])
    assert response.provider == "primary"
    assert provider.availability_calls == 1
    assert provider.generation_calls == 1


class OversizeProvider(LLMInterface):
    def __init__(self, name: str = "primary"):
        self.name = name
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        exc = RuntimeError(
            "Error code: 413 - Request too large for model on tokens per minute (TPM); rate_limit_exceeded"
        )
        exc.status_code = 413
        raise exc

    def is_available(self):
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return "oversize"


def test_request_too_large_falls_through_without_rate_limit_cooldown():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]

    router = LLMRouter(config)
    primary = OversizeProvider("primary")
    router.register_provider("primary", primary)
    router.register_provider("secondary", GoodProvider("secondary"))

    first = router.generate([LLMMessage(role="user", content="hello")])
    assert first.provider == "secondary"
    assert router._cooldown_remaining("primary") == 0

    second = router.generate([LLMMessage(role="user", content="hello again")])
    assert second.provider == "secondary"
    assert primary.calls == 2
    assert router.last_generation_attempts[0]["provider"] == "primary"
    assert router.last_generation_attempts[0]["status"] == "failed"
