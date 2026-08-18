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
