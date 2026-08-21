from __future__ import annotations

from unittest.mock import patch

from mary.core.config import Config
from mary.core.mary import Mary
from mary.cognition.intent import IntentType
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.environment import RuntimeEnvironment
from mary.runtime.introspection import RuntimeIntrospection, is_personal_runtime_reaction


class CapturingProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True, model: str | None = None):
        self.name = name
        self.available = available
        self.model = model or f"{name}-test"
        self.calls = 0
        self.last_messages = []

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        self.last_messages = list(messages)
        return LLMResponse(
            content=(
                "That is pretty cool. Same me, different machine. "
                "I do not have Ollama available here, so I am using the providers this host actually has."
            ),
            provider=self.name,
            model=self.model,
            finish_reason="stop",
        )

    def is_available(self) -> bool:
        return self.available

    def provider_name(self) -> str:
        return self.name

    def model_name(self) -> str:
        return self.model


def _router(*, ollama: bool = False):
    config = Config()
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)
    providers = {
        "ollama": CapturingProvider("ollama", available=ollama, model="qwen3:4b-instruct"),
        "groq": CapturingProvider("groq", model="openai/gpt-oss-20b"),
        "gemini": CapturingProvider("gemini", model="gemini-3.6-flash"),
        "openrouter": CapturingProvider("openrouter", model="openrouter/free"),
        "openai": CapturingProvider("openai", available=False, model="gpt-5.6-luna"),
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return config, router, providers


def _wire(mary: Mary, config: Config, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.conversation.router = router
    mary.runtime_environment = RuntimeEnvironment(config=config, router=router)
    mary.runtime_introspection = RuntimeIntrospection()


def _clear_host_env(monkeypatch) -> None:
    for name in (
        "REPL_ID", "REPL_SLUG", "REPL_OWNER", "REPLIT_DB_URL",
        "CODESPACES", "CODESPACE_NAME",
    ):
        monkeypatch.delenv(name, raising=False)


def test_macbook_first_time_reaction_is_personal_not_runtime_dump(monkeypatch):
    _clear_host_env(monkeypatch)
    mary = Mary()
    config, router, providers = _router(ollama=False)
    _wire(mary, config, router)

    with patch("mary.runtime.environment.platform.system", return_value="Darwin"):
        result = mary.process("hey Mary, we're running on my MacBook for the first time. what do you think?")

    assert result.intent.intent_type != IntentType.SELF_QUERY
    assert result.reasoning.metadata["generation_purpose"] == "conversation"
    assert result.reasoning.metadata["turn_policy"]["category"] == "personal_conversation"
    assert providers["groq"].calls >= 1
    assert "same me, different machine" in result.final_response.lower()


def test_hybrid_runtime_turn_injects_grounded_macos_context(monkeypatch):
    _clear_host_env(monkeypatch)
    mary = Mary()
    config, router, providers = _router(ollama=False)
    _wire(mary, config, router)

    with patch("mary.runtime.environment.platform.system", return_value="Darwin"):
        mary.process("we're running on my MacBook for the first time what do u think")

    combined = "\n".join(str(message.content) for message in providers["groq"].last_messages)
    assert "runtime_context" in combined
    assert "macos" in combined
    assert "groq" in combined
    assert "ollama" in combined
    assert "do not recite a diagnostic report" in combined.lower()


def test_pure_models_question_remains_deterministic_runtime_introspection(monkeypatch):
    _clear_host_env(monkeypatch)
    mary = Mary()
    config, router, providers = _router(ollama=False)
    _wire(mary, config, router)

    with patch("mary.runtime.environment.platform.system", return_value="Darwin"):
        result = mary.process("what models can you use right now?")

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.reasoning.metadata["generation_purpose"] == "runtime_introspection"
    assert result.reasoning.metadata["turn_policy"]["category"] == "local_runtime"
    assert providers["groq"].calls == 0


def test_pure_host_change_question_remains_deterministic(monkeypatch):
    _clear_host_env(monkeypatch)
    mary = Mary()
    config, router, providers = _router(ollama=False)
    _wire(mary, config, router)

    with patch("mary.runtime.environment.platform.system", return_value="Darwin"):
        result = mary.process("does anything about how you work change because were not on my pc?")

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert providers["groq"].calls == 0
    assert "this host changes which capabilities" in result.final_response.lower()


def test_hybrid_classifier_is_conservative():
    assert is_personal_runtime_reaction("we're running on my MacBook for the first time what do you think?") is True
    assert is_personal_runtime_reaction("idk im working on u from replit on my phone right now what do u think") is True
    assert is_personal_runtime_reaction("what models can you use right now?") is False
    assert is_personal_runtime_reaction("where are you running right now?") is False
    assert is_personal_runtime_reaction("does anything about how you work change because were not on my pc?") is False
