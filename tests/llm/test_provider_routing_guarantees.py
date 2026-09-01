from __future__ import annotations

import pytest

from mary.core.config import Config
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMRateLimitError,
    LLMResponse,
)
from mary.llm.router import LLMRouter


class FakeProvider(LLMInterface):
    """Deterministic provider used to prove routing without network calls."""

    def __init__(
        self,
        name: str,
        *,
        available: bool = True,
        availability_error: Exception | None = None,
        generation_error: Exception | None = None,
        finish_reason: str | None = None,
    ) -> None:
        self.name = name
        self.available = available
        self.availability_error = availability_error
        self.generation_error = generation_error
        self.finish_reason = finish_reason
        self.availability_checks = 0
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        if self.generation_error is not None:
            raise self.generation_error
        return LLMResponse(
            content=f"{self.name} response",
            provider=self.name,
            model=f"fake-{self.name}",
            finish_reason=self.finish_reason,
        )

    def is_available(self):
        self.availability_checks += 1
        if self.availability_error is not None:
            raise self.availability_error
        return self.available

    def provider_name(self):
        return self.name

    def model_name(self):
        return f"fake-{self.name}"


def _free_first_router() -> tuple[LLMRouter, dict[str, FakeProvider]]:
    config = Config()
    config.llm.provider = "groq"
    config.llm.routing_strategy = "free_first"
    config.llm.free_provider_order = [
        "groq",
        "gemini",
        "openrouter",
        "ollama",
    ]

    router = LLMRouter(config)
    providers = {
        name: FakeProvider(name)
        for name in ("groq", "gemini", "openrouter", "ollama", "openai")
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def _message() -> list[LLMMessage]:
    return [LLMMessage(role="user", content="routing guarantee test")]


def test_groq_success_stops_the_free_first_route():
    router, providers = _free_first_router()

    response = router.generate(_message())

    assert response.provider == "groq"
    assert providers["groq"].calls == 1
    assert providers["gemini"].calls == 0
    assert providers["openrouter"].calls == 0
    assert providers["ollama"].calls == 0
    assert [(item["provider"], item["status"]) for item in router.last_generation_attempts] == [
        ("groq", "success"),
    ]


def test_groq_failure_falls_through_to_gemini():
    router, providers = _free_first_router()
    providers["groq"].generation_error = RuntimeError("groq failed")

    response = router.generate(_message())

    assert response.provider == "gemini"
    assert providers["groq"].calls == 1
    assert providers["gemini"].calls == 1
    assert providers["openrouter"].calls == 0
    assert providers["ollama"].calls == 0
    assert [item["provider"] for item in router.last_generation_attempts] == [
        "groq",
        "gemini",
    ]


def test_groq_and_gemini_failure_reaches_openrouter():
    router, providers = _free_first_router()
    providers["groq"].generation_error = RuntimeError("groq failed")
    providers["gemini"].generation_error = RuntimeError("gemini failed")

    response = router.generate(_message())

    assert response.provider == "openrouter"
    assert providers["openrouter"].calls == 1
    assert providers["ollama"].calls == 0
    assert [item["provider"] for item in router.last_generation_attempts] == [
        "groq",
        "gemini",
        "openrouter",
    ]


def test_cloud_free_failures_reach_ollama():
    router, providers = _free_first_router()
    for name in ("groq", "gemini", "openrouter"):
        providers[name].generation_error = RuntimeError(f"{name} failed")

    response = router.generate(_message())

    assert response.provider == "ollama"
    assert providers["ollama"].calls == 1
    assert [item["provider"] for item in router.last_generation_attempts] == [
        "groq",
        "gemini",
        "openrouter",
        "ollama",
    ]


@pytest.mark.parametrize("route", ["private", "local", "offline"])
def test_private_routes_are_ollama_only(route):
    router, providers = _free_first_router()

    response = router.generate(
        _message(),
        provider="openai",
        route=route,
    )

    assert response.provider == "ollama"
    assert providers["ollama"].calls == 1
    for name in ("groq", "gemini", "openrouter", "openai"):
        assert providers[name].calls == 0
    assert [(item["provider"], item["status"]) for item in router.last_generation_attempts] == [
        ("ollama", "success"),
    ]


def test_paid_openai_never_silently_enters_free_first():
    router, providers = _free_first_router()
    router.config.llm.provider = "openai"
    router.config.llm.fallback_providers = ["openai"]
    for name in ("groq", "gemini", "openrouter"):
        providers[name].generation_error = RuntimeError(f"{name} failed")

    response = router.generate(_message())

    assert response.provider == "ollama"
    assert providers["openai"].availability_checks == 0
    assert providers["openai"].calls == 0
    assert "openai" not in [
        item["provider"]
        for item in router.last_generation_attempts
    ]


def test_not_configured_provider_is_skipped_without_generation():
    router, providers = _free_first_router()
    providers["groq"].available = False

    response = router.generate(_message())

    assert response.provider == "gemini"
    assert providers["groq"].calls == 0
    assert router.last_generation_attempts[0]["provider"] == "groq"
    assert router.last_generation_attempts[0]["status"] == "not_configured"
    assert router.last_generation_attempts[0]["failure_category"] == "not_configured"
    assert "error" not in router.last_generation_attempts[0]


def test_availability_check_failure_is_skipped_as_unavailable():
    router, providers = _free_first_router()
    providers["groq"].availability_error = RuntimeError("health check failed")

    response = router.generate(_message())

    assert response.provider == "gemini"
    assert providers["groq"].calls == 0
    assert router.last_generation_attempts[0]["provider"] == "groq"
    assert router.last_generation_attempts[0]["status"] == "unavailable"
    assert router.last_generation_attempts[0]["failure_category"] == "provider_error"
    assert "error" not in router.last_generation_attempts[0]


def test_incomplete_length_response_falls_through_instead_of_being_spoken():
    router, providers = _free_first_router()
    providers["groq"].generation_error = RuntimeError("groq failed")
    providers["gemini"].finish_reason = "length"

    response = router.generate(_message())

    assert response.provider == "openrouter"
    assert providers["gemini"].calls == 1
    assert [
        (item["provider"], item["status"])
        for item in router.last_generation_attempts
    ] == [
        ("groq", "failed"),
        ("gemini", "incomplete"),
        ("openrouter", "success"),
    ]
    assert all("error" not in item for item in router.last_generation_attempts)


def test_rate_limit_cooldown_skips_provider_on_next_turn_without_extra_call():
    router, providers = _free_first_router()
    providers["groq"].generation_error = LLMRateLimitError(
        "groq quota reached",
        provider="groq",
    )

    first = router.generate(_message())
    second = router.generate(_message())

    assert first.provider == "gemini"
    assert second.provider == "gemini"
    assert providers["groq"].calls == 1
    assert providers["gemini"].calls == 2
    assert router.last_generation_attempts[0]["provider"] == "groq"
    assert router.last_generation_attempts[0]["status"] == "cooldown"
    assert router.last_generation_attempts[1]["provider"] == "gemini"
    assert router.last_generation_attempts[1]["status"] == "success"


def test_provider_attempts_reports_exact_route_results():
    router, providers = _free_first_router()
    providers["groq"].generation_error = RuntimeError("groq failed")
    providers["gemini"].available = False

    response = router.generate(_message())

    assert response.provider == "openrouter"
    assert [
        (item["provider"], item["status"])
        for item in router.last_generation_attempts
    ] == [
        ("groq", "failed"),
        ("gemini", "not_configured"),
        ("openrouter", "success"),
    ]
    assert all("error" not in item for item in router.last_generation_attempts)


def test_explicit_provider_override_bypasses_free_first_order():
    router, providers = _free_first_router()
    router.config.llm.fallback_providers = ["ollama"]

    response = router.generate(
        _message(),
        provider="gemini",
    )

    assert response.provider == "gemini"
    assert providers["groq"].availability_checks == 0
    assert providers["groq"].calls == 0
    assert providers["gemini"].calls == 1
    assert providers["openrouter"].calls == 0
    assert providers["ollama"].calls == 0
    assert [(item["provider"], item["status"]) for item in router.last_generation_attempts] == [
        ("gemini", "success"),
    ]
