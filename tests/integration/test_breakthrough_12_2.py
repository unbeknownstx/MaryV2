from __future__ import annotations

from unittest.mock import patch

from mary.core.config import Config
from mary.core.mary import Mary
from mary.cognition.intent import IntentType
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.environment import RuntimeEnvironment
from mary.runtime.introspection import RuntimeIntrospection


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


def _router(*, ollama: bool, openai: bool = False):
    config = Config()
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)
    providers = {
        "ollama": FakeProvider("ollama", available=ollama, model="qwen3:4b-instruct"),
        "groq": FakeProvider("groq", model="openai/gpt-oss-20b"),
        "gemini": FakeProvider("gemini", model="gemini-3.6-flash"),
        "openrouter": FakeProvider("openrouter", model="openrouter/free"),
        "openai": FakeProvider("openai", available=openai, model="gpt-5.6-luna"),
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
        "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID", "RAILWAY_SERVICE_ID",
        "MARY_RUNTIME_ROLE",
    ):
        monkeypatch.delenv(name, raising=False)


def _simulate_replit(monkeypatch) -> None:
    """Simulate the real Replit host independently of the machine running pytest."""

    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "portable-test")
    monkeypatch.setattr(
        "mary.runtime.environment.platform.system",
        lambda: "Linux",
    )


def test_models_question_is_concise_runtime_answer_on_replit(monkeypatch):
    _simulate_replit(monkeypatch)
    mary = Mary()
    config, router, providers = _router(ollama=False)
    _wire(mary, config, router)

    result = mary.process("what models can you use right now?")
    text = result.final_response.lower()

    assert "right now on replit / linux" in text
    assert "groq" in text and "gemini" in text and "openrouter" in text
    assert "ollama" in text
    assert "my identity, memory, personality" not in text
    assert providers["groq"].calls == 0
    assert result.reasoning.metadata["generation_purpose"] == "runtime_introspection"
    assert result.reasoning.metadata["turn_policy"]["category"] == "local_runtime"


def test_host_change_question_gets_portability_answer_not_architecture_dump(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "portable-test")
    mary = Mary()
    config, router, _ = _router(ollama=False)
    _wire(mary, config, router)

    result = mary.process("does anything about how you work change because were not on my pc?")
    text = result.final_response.lower()

    assert "my core maryv2 architecture does not change" in text
    assert "this host changes which capabilities" in text
    assert "effective conversation route" in text
    assert "language models are routed generation engines" not in text


def test_where_are_you_running_is_host_only_answer(monkeypatch):
    _simulate_replit(monkeypatch)
    mary = Mary()
    config, router, _ = _router(ollama=False)
    _wire(mary, config, router)

    result = mary.process("where are you running right now?")
    text = result.final_response.lower()

    assert text.startswith("i'm running on replit / linux")
    assert "desktop ui is not available" in text
    assert "my identity, memory, personality" not in text


def test_ollama_specific_question_reports_unavailable_without_llm(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "portable-test")
    mary = Mary()
    config, router, providers = _router(ollama=False)
    _wire(mary, config, router)

    result = mary.process("can u use ollama here?")
    text = result.final_response.lower()

    assert "ollama is configured" in text
    assert "not reachable/available on this host" in text
    assert providers["groq"].calls == 0


def test_openai_specific_answer_preserves_explicit_expert_boundary(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "portable-test")
    mary = Mary()
    config, router, _ = _router(ollama=False, openai=True)
    _wire(mary, config, router)

    result = mary.process("can you use openai right now?")
    text = result.final_response.lower()

    assert "explicitly authorized one-task expert" in text


def test_runtime_last_metadata_is_truthful_and_specific(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "portable-test")
    mary = Mary()
    config, router, _ = _router(ollama=False)
    _wire(mary, config, router)

    result = mary.process("what models can you use right now?")
    meta = result.reasoning.metadata

    assert meta["provider"] == "local/system"
    assert meta["model"] == "n/a"
    assert meta["generation_purpose"] == "runtime_introspection"
    assert meta["turn_policy"]["category"] == "local_runtime"
    assert meta["self_grounded"] is True


def test_broad_architecture_question_still_gets_full_architecture_answer(monkeypatch):
    _simulate_replit(monkeypatch)
    mary = Mary()
    config, router, _ = _router(ollama=False)
    _wire(mary, config, router)

    result = mary.process("what is your underlying architecture?")
    text = result.final_response.lower()

    assert "my identity, memory, personality" in text
    assert "language models are routed generation engines" in text
    assert "replit / linux" in text


def test_external_latest_model_question_is_still_web_intent():
    mary = Mary()
    intent = mary.cognition.detect_intent("what is the latest OpenAI model right now?")
    assert intent.intent_type == IntentType.WEB_SEARCH


def test_portability_matrix_windows_with_ollama(monkeypatch):
    _clear_host_env(monkeypatch)
    config, router, _ = _router(ollama=True)
    with patch("mary.runtime.environment.platform.system", return_value="Windows"):
        snap = RuntimeEnvironment(config=config, router=router).snapshot()
    assert snap["host_type"] == "local_development"
    assert snap["platform"] == "windows"
    assert snap["effective_conversation_route"][0] == "ollama"


def test_portability_matrix_windows_without_ollama(monkeypatch):
    _clear_host_env(monkeypatch)
    config, router, _ = _router(ollama=False)
    with patch("mary.runtime.environment.platform.system", return_value="Windows"):
        snap = RuntimeEnvironment(config=config, router=router).snapshot()
    assert snap["platform"] == "windows"
    assert snap["effective_conversation_route"] == ["groq", "gemini", "openrouter"]


def test_portability_matrix_macos_without_ollama(monkeypatch):
    _clear_host_env(monkeypatch)
    config, router, _ = _router(ollama=False)
    with patch("mary.runtime.environment.platform.system", return_value="Darwin"):
        snap = RuntimeEnvironment(config=config, router=router).snapshot()
    assert snap["platform"] == "macos"
    assert snap["capabilities"]["desktop_ui"] is True
    assert snap["effective_conversation_route"] == ["groq", "gemini", "openrouter"]


def test_portability_matrix_macos_with_ollama(monkeypatch):
    _clear_host_env(monkeypatch)
    config, router, _ = _router(ollama=True)
    with patch("mary.runtime.environment.platform.system", return_value="Darwin"):
        snap = RuntimeEnvironment(config=config, router=router).snapshot()
    assert snap["platform"] == "macos"
    assert snap["effective_conversation_route"][0] == "ollama"


def test_portability_matrix_codespaces_beats_inherited_replit_markers(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "ambient-replit")
    monkeypatch.setenv("CODESPACES", "true")
    config, router, _ = _router(ollama=False)
    snap = RuntimeEnvironment(config=config, router=router).snapshot()
    assert snap["host_type"] == "codespaces"
    assert snap["effective_conversation_route"] == ["groq", "gemini", "openrouter"]


def test_portability_matrix_replit_has_no_desktop_hardware_capabilities(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("REPL_ID", "portable-test")
    config, router, _ = _router(ollama=False)
    snap = RuntimeEnvironment(config=config, router=router).snapshot()
    assert snap["host_type"] == "replit"
    assert snap["capabilities"]["desktop_ui"] is False
    assert snap["capabilities"]["native_microphone"] is False
    assert snap["capabilities"]["avatar"] is False



def test_portability_matrix_railway_core_has_no_desktop_hardware_capabilities(monkeypatch):
    _clear_host_env(monkeypatch)
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "mary-core-test")
    monkeypatch.setenv("MARY_RUNTIME_ROLE", "core")
    config, router, _ = _router(ollama=False)

    snap = RuntimeEnvironment(config=config, router=router).snapshot()

    assert snap["host_type"] == "railway"
    assert snap["runtime_role"] == "core"
    assert snap["capabilities"]["desktop_ui"] is False
    assert snap["capabilities"]["native_microphone"] is False
    assert snap["capabilities"]["native_audio"] is False
    assert snap["capabilities"]["avatar"] is False

def test_runtime_introspection_and_environment_versions_are_current():
    assert RuntimeEnvironment.VERSION == "v2-breakthrough-12.2"
    assert RuntimeIntrospection.VERSION in {"v2-breakthrough-12.2", "v2-breakthrough-12.3"}
