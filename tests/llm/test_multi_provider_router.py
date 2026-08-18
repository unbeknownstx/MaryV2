import os
from unittest.mock import patch

from mary.core.config import Config
from mary.llm.router import LLMRouter


def test_router_constructs_new_provider_types():
    r = LLMRouter(Config())
    with patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "x",
            "OPENROUTER_API_KEY": "x",
        },
    ):
        assert r._create_provider("gemini").provider_name() == "gemini"
        assert r._create_provider("openrouter").provider_name() == "openrouter"
    assert r._create_provider("ollama").provider_name() == "ollama"


def test_free_first_environment_provider_order(monkeypatch):
    monkeypatch.setenv("MARY_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MARY_LLM_ROUTING_STRATEGY", "free_first")
    monkeypatch.setenv(
        "MARY_LLM_FREE_ORDER",
        "groq,gemini,openrouter,ollama",
    )
    monkeypatch.setenv(
        "MARY_LLM_FALLBACKS",
        "openai",
    )

    config = Config.from_environment()
    router = LLMRouter(config)

    assert router._provider_order(None) == [
        "groq",
        "gemini",
        "openrouter",
        "ollama",
    ]


def test_configured_strategy_preserves_legacy_order(monkeypatch):
    monkeypatch.setenv("MARY_LLM_PROVIDER", "groq")
    monkeypatch.setenv(
        "MARY_LLM_ROUTING_STRATEGY",
        "configured",
    )
    monkeypatch.setenv(
        "MARY_LLM_FALLBACKS",
        "gemini,openrouter,ollama,openai",
    )

    config = Config.from_environment()
    router = LLMRouter(config)

    assert router._provider_order(None) == [
        "groq",
        "gemini",
        "openrouter",
        "ollama",
        "openai",
    ]


def test_private_route_forces_ollama():
    router = LLMRouter(Config())

    assert router._provider_order(
        None,
        route="private",
    ) == ["ollama"]


def test_free_first_openrouter_rejects_accidental_paid_model(monkeypatch):
    monkeypatch.setenv(
        "MARY_OPENROUTER_MODEL",
        "some-provider/paid-model",
    )

    config = Config()
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)

    provider = router._create_provider("openrouter")

    assert provider.model_name() == "openrouter/free"


def test_free_first_openrouter_allows_specific_free_model(monkeypatch):
    monkeypatch.setenv(
        "MARY_OPENROUTER_MODEL",
        "some-provider/model:free",
    )

    config = Config()
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)

    provider = router._create_provider("openrouter")

    assert provider.model_name() == "some-provider/model:free"
