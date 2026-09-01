from __future__ import annotations

import pytest

from mary.cognition.intent import IntentType
from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.application import MaryApplication, create_application


_applications: list[MaryApplication] = []


def _run(app: MaryApplication, input_text: str):
    return app.run(input_text).metadata["pipeline_values"]["cognitive_cycle"]


def _application() -> MaryApplication:
    app = create_application(
        auto_save=False, load_memory=False, load_developed_self=False,
        load_preference_promotion=False, load_knowledge=False,
    )
    _applications.append(app)
    return app


@pytest.fixture(autouse=True)
def _close_applications():
    yield
    while _applications:
        _applications.pop().close()


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True, content: str | None = None) -> None:
        self.name = name
        self.available = available
        self.content = content or f"{name} response"
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(
            content=self.content,
            provider=self.name,
            model=f"fake-{self.name}",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    def is_available(self):
        return self.available

    def provider_name(self):
        return self.name

    def model_name(self):
        return f"fake-{self.name}"


def _router(*, ollama_available: bool = True) -> tuple[LLMRouter, dict[str, FakeProvider]]:
    config = Config()
    config.llm.provider = "groq"
    config.llm.routing_strategy = "free_first"
    config.llm.free_provider_order = ["groq", "gemini", "openrouter", "ollama"]
    config.llm.conversation_provider_order = ["ollama", "groq", "gemini", "openrouter"]
    router = LLMRouter(config)
    providers = {
        "groq": FakeProvider("groq"),
        "gemini": FakeProvider("gemini"),
        "openrouter": FakeProvider("openrouter"),
        "ollama": FakeProvider("ollama", available=ollama_available),
        "openai": FakeProvider("openai"),
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def _wire(mary: Mary, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router


def test_default_conversation_order_is_local_first():
    router, _ = _router()
    assert router._provider_order(None, purpose="conversation") == [
        "ollama", "groq", "gemini", "openrouter"
    ]


def test_default_task_general_order_remains_cloud_first():
    router, _ = _router()
    assert router._provider_order(None) == [
        "groq", "gemini", "openrouter", "ollama"
    ]


def test_conversation_purpose_uses_ollama_first():
    router, providers = _router()
    result = router.generate(
        [LLMMessage(role="user", content="just talk with me")],
        purpose="conversation",
    )
    assert result.provider == "ollama"
    assert providers["ollama"].calls == 1
    assert providers["groq"].calls == 0


def test_conversation_falls_back_to_free_cloud_if_ollama_is_unavailable():
    router, providers = _router(ollama_available=False)
    result = router.generate(
        [LLMMessage(role="user", content="just talk with me")],
        purpose="conversation",
    )
    assert result.provider == "groq"
    assert providers["groq"].calls == 1


def test_session_override_beats_default_conversation_policy():
    router, providers = _router()
    router.set_session_override(provider="gemini")
    result = router.generate(
        [LLMMessage(role="user", content="just talk with me")],
        purpose="conversation",
    )
    assert result.provider == "gemini"
    assert providers["gemini"].calls == 1
    assert providers["ollama"].calls == 0


def test_natural_go_into_ollama_phrase_is_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    intent = mary.cognition.detect_intent("go into ollama llm")
    assert intent.intent_type == IntentType.TOOL_USE
    assert intent.parameters["operation"] == "set_session"
    assert intent.parameters["route"] == "private"


def test_how_can_i_let_you_use_ollama_is_runtime_query_not_model_guess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    intent = mary.cognition.detect_intent("how can i let you use ollama?")
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_normal_mary_conversation_uses_local_first_without_manual_switch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    router, providers = _router()
    providers["ollama"].content = "Yeah, I'm here. We can just talk."
    _wire(mary, router)

    result = _run(app, "idk i just wanna talk for a bit")

    assert result.reasoning.metadata["provider"] == "ollama"
    assert result.reasoning.metadata["generation_purpose"] == "conversation"
    assert providers["ollama"].calls >= 1
    assert providers["groq"].calls == 0


def test_request_intent_keeps_task_general_route_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    router, providers = _router()
    _wire(mary, router)

    # Force a task-shaped intent so the test checks routing policy rather than
    # the natural-language intent detector's wording coverage.
    intent = mary.cognition.detect_intent("create file test.txt with hello")
    assert intent.intent_type == IntentType.TOOL_USE

    # Direct task/general router use remains cloud-first when no conversation
    # purpose is supplied.
    result = router.generate([LLMMessage(role="user", content="task synthesis")])
    assert result.provider == "groq"
    assert providers["groq"].calls == 1


def test_status_exposes_both_conversation_and_task_routes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    status = mary.status()["cognition"]
    assert status["provider_order"][0] == "groq"
    assert status["conversation_provider_order"][0] == "ollama"
