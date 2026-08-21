from __future__ import annotations

from mary.core.config import Config
from mary.core.mary import Mary
from mary.cognition.intent import IntentType
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.environment import RuntimeEnvironment


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True, model: str | None = None):
        self.name = name
        self.available = available
        self.model = model or f"{name}-test"
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(
            content=f"response from {self.name}",
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


def _router(*, ollama=False):
    config = Config()
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)
    providers = {
        "ollama": FakeProvider("ollama", available=ollama, model="qwen3:4b-instruct"),
        "groq": FakeProvider("groq"),
        "gemini": FakeProvider("gemini"),
        "openrouter": FakeProvider("openrouter"),
        "openai": FakeProvider("openai"),
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def _wire(mary: Mary, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.conversation.router = router
    mary.runtime_environment = RuntimeEnvironment(config=mary.config, router=router)


def test_replit_host_is_detected(monkeypatch):
    monkeypatch.setenv("REPL_ID", "test-repl")
    router, _ = _router(ollama=False)
    env = RuntimeEnvironment(config=Config(), router=router)
    assert env.snapshot()["host_type"] == "replit"


def test_codespaces_host_is_detected(monkeypatch):
    monkeypatch.delenv("REPL_ID", raising=False)
    monkeypatch.setenv("CODESPACES", "true")
    router, _ = _router(ollama=False)
    env = RuntimeEnvironment(config=Config(), router=router)
    assert env.snapshot()["host_type"] == "codespaces"


def test_replit_effective_conversation_route_skips_unavailable_ollama(monkeypatch):
    monkeypatch.setenv("REPL_ID", "test-repl")
    router, _ = _router(ollama=False)
    env = RuntimeEnvironment(config=Config(), router=router)
    snap = env.snapshot()
    assert snap["conversation_policy"][0] == "ollama"
    assert snap["effective_conversation_route"] == ["groq", "gemini", "openrouter"]


def test_local_host_can_keep_ollama_first_when_available(monkeypatch):
    monkeypatch.delenv("REPL_ID", raising=False)
    monkeypatch.delenv("REPL_SLUG", raising=False)
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.delenv("CODESPACE_NAME", raising=False)
    router, _ = _router(ollama=True)
    env = RuntimeEnvironment(config=Config(), router=router)
    assert env.snapshot()["effective_conversation_route"][0] == "ollama"


def test_models_available_right_now_is_runtime_self_query_not_web():
    mary = Mary()
    intent = mary.cognition.detect_intent("what models can u use right now?")
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_not_on_my_pc_question_is_runtime_self_query_not_web():
    mary = Mary()
    intent = mary.cognition.detect_intent("does anything change because were not on my pc?")
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_replit_personal_sentence_with_right_now_stays_conversation_not_web():
    mary = Mary()
    intent = mary.cognition.detect_intent(
        "idk im working on u from replit on my phone right now what do u think about that?"
    )
    assert intent.intent_type != IntentType.WEB_SEARCH


def test_latest_python_release_still_routes_to_web():
    mary = Mary()
    intent = mary.cognition.detect_intent("what is the latest Python release?")
    assert intent.intent_type == IntentType.WEB_SEARCH


def test_latest_game_news_right_now_still_routes_to_web():
    mary = Mary()
    intent = mary.cognition.detect_intent("what is the latest game news right now?")
    assert intent.intent_type == IntentType.WEB_SEARCH


def test_runtime_environment_response_reports_host_and_effective_route(monkeypatch):
    monkeypatch.setenv("REPL_ID", "test-repl")
    mary = Mary()
    router, _ = _router(ollama=False)
    _wire(mary, router)
    response = mary._runtime_architecture_response(query="what models can u use right now?")
    lowered = response.lower()
    assert "replit" in lowered
    assert "ollama is not reachable" in lowered
    assert "groq -> gemini -> openrouter" in lowered


def test_replit_conversation_generation_skips_unavailable_ollama(monkeypatch):
    monkeypatch.setenv("REPL_ID", "test-repl")
    mary = Mary()
    router, providers = _router(ollama=False)
    _wire(mary, router)
    result = mary.process("idk i just wanna talk for a bit")
    assert result.reasoning.metadata["provider"] == "groq"
    assert providers["ollama"].calls == 0
    assert providers["groq"].calls >= 1


def test_environment_snapshot_is_display_safe(monkeypatch):
    monkeypatch.setenv("REPL_ID", "test-repl")
    router, _ = _router(ollama=False)
    snap = RuntimeEnvironment(config=Config(), router=router).snapshot()
    text = str(snap)
    assert "API_KEY" not in text
    assert "sk-" not in text
    assert "prompt" not in text.lower()


def test_models_available_typo_still_routes_to_runtime_not_llm():
    mary = Mary()
    intent = mary.cognition.detect_intent("what models can you ise right now?")
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_natural_not_on_pc_wording_routes_to_runtime_not_llm():
    mary = Mary()
    intent = mary.cognition.detect_intent(
        "does anything about how you work change because were not on my pc?"
    )
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_provider_runtime_guard_does_not_steal_external_model_news():
    mary = Mary()
    intent = mary.cognition.detect_intent("what is the latest OpenAI model right now?")
    assert intent.intent_type == IntentType.WEB_SEARCH
