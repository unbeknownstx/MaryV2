from __future__ import annotations

import sys
import types

from mary.core.config import Config
from mary.llm.router import LLMRouter


def _fake_groq(monkeypatch):
    module = types.ModuleType("mary.llm.providers.groq")

    class FakeGroqProvider:
        def __init__(self, model):
            self.model = model

        def model_name(self):
            return self.model

        def is_available(self):
            return True

    module.GroqProvider = FakeGroqProvider
    monkeypatch.setitem(sys.modules, "mary.llm.providers.groq", module)


def test_provider_specific_groq_model_wins_over_legacy_primary(monkeypatch):
    _fake_groq(monkeypatch)
    monkeypatch.setenv("MARY_LLM_PROVIDER", "groq")
    monkeypatch.setenv("MARY_LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("MARY_GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.delenv("MARY_GROQ_CONVERSATION_MODEL", raising=False)

    router = LLMRouter(Config.from_environment())

    assert router.get_provider("groq").model_name() == "llama-3.1-8b-instant"
    assert router.model_name("groq") == "llama-3.1-8b-instant"


def test_social_groq_inherits_provider_specific_model_when_no_chat_override(monkeypatch):
    _fake_groq(monkeypatch)
    monkeypatch.setenv("MARY_LLM_PROVIDER", "groq")
    monkeypatch.setenv("MARY_LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("MARY_GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.delenv("MARY_GROQ_CONVERSATION_MODEL", raising=False)

    router = LLMRouter(Config.from_environment())
    provider = router._get_provider_for_purpose("groq", "social_instant")

    assert provider.model_name() == "llama-3.1-8b-instant"


def test_explicit_social_groq_model_still_wins(monkeypatch):
    _fake_groq(monkeypatch)
    monkeypatch.setenv("MARY_GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("MARY_GROQ_CONVERSATION_MODEL", "llama-3.1-8b-instant")

    router = LLMRouter(Config.from_environment())
    provider = router._get_provider_for_purpose("groq", "social_instant")

    assert provider.model_name() == "llama-3.1-8b-instant"


def test_legacy_llm_model_remains_fallback_for_groq(monkeypatch):
    _fake_groq(monkeypatch)
    monkeypatch.setenv("MARY_LLM_PROVIDER", "groq")
    monkeypatch.setenv("MARY_LLM_MODEL", "legacy-groq-model")
    monkeypatch.delenv("MARY_GROQ_MODEL", raising=False)
    monkeypatch.delenv("MARY_GROQ_CONVERSATION_MODEL", raising=False)

    router = LLMRouter(Config.from_environment())

    assert router.get_provider("groq").model_name() == "legacy-groq-model"
    assert (
        router._get_provider_for_purpose("groq", "social_instant").model_name()
        == "legacy-groq-model"
    )
