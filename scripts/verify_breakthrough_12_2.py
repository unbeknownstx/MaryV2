"""Deterministic verification for Breakthrough 12.2 runtime introspection polish."""

from __future__ import annotations

import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from mary.core.config import Config
from mary.cognition.intent import IntentType
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.environment import RuntimeEnvironment
from mary.runtime.introspection import RuntimeIntrospection
from mary.runtime.application import create_application


class FakeProvider(LLMInterface):
    def __init__(self, name: str, available: bool = True, model: str | None = None):
        self.name = name
        self.available = available
        self.model = model or f"{name}-test"
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(f"{self.name} answer", self.name, self.model, "stop")

    def is_available(self): return self.available
    def provider_name(self): return self.name
    def model_name(self): return self.model


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def _router(ollama: bool = False, openai: bool = False):
    config = Config()
    router = LLMRouter(config)
    providers = {
        "ollama": FakeProvider("ollama", ollama, "qwen3:4b-instruct"),
        "groq": FakeProvider("groq", True, "openai/gpt-oss-20b"),
        "gemini": FakeProvider("gemini", True, "gemini-3.6-flash"),
        "openrouter": FakeProvider("openrouter", True, "openrouter/free"),
        "openai": FakeProvider("openai", openai, "gpt-5.6-luna"),
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return config, router, providers


def _wire(mary, config, router) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.conversation.router = router
    mary.runtime_environment = RuntimeEnvironment(config=config, router=router)
    mary.runtime_introspection = RuntimeIntrospection()


def main() -> None:
    print("=" * 72)
    print("MARY V2 BREAKTHROUGH 12.2 - RUNTIME INTROSPECTION / PORTABILITY POLISH")
    print("=" * 72)

    with tempfile.TemporaryDirectory(prefix="maryv2_bt12_2_") as directory, ExitStack() as cleanup, patch.dict(os.environ, {"REPL_ID": "verification-repl"}, clear=False), patch(
        "mary.runtime.environment.platform.system",
        return_value="Linux",
    ):
        os.environ.pop("CODESPACES", None)
        os.environ.pop("CODESPACE_NAME", None)
        config, router, providers = _router(ollama=False, openai=True)
        app = create_application(
            memory_path=Path(directory) / "data" / "memory" / "memory.json",
            auto_save=False, load_memory=False, load_developed_self=False,
            load_preference_promotion=False, load_knowledge=False,
        )
        cleanup.callback(app.close)
        mary = app.mary
        _wire(mary, config, router)

        result = _turn(app, "what models can you use right now?")
        text = result.final_response.lower()
        check("provider question is concise and host-specific", "right now on replit / linux" in text and "my identity, memory, personality" not in text)
        check("provider question uses zero generation calls", sum(provider.calls for provider in providers.values()) == 0)
        check("runtime turn metadata is explicit", result.reasoning.metadata.get("generation_purpose") == "runtime_introspection" and result.reasoning.metadata.get("turn_policy", {}).get("category") == "local_runtime")

        result = _turn(app, "does anything about how you work change because were not on my pc?")
        check("host-change question explains capabilities rather than dumping architecture", "this host changes which capabilities" in result.final_response.lower())

        result = _turn(app, "where are you running right now?")
        check("host question answers host/platform directly", result.final_response.lower().startswith("i'm running on replit / linux"))

        result = _turn(app, "can u use ollama here?")
        check("provider-specific question reports Ollama unavailable truthfully", "not reachable/available on this host" in result.final_response.lower())

        intent = mary.cognition.detect_intent("what is the latest OpenAI model right now?")
        check("external latest-model question still routes to web", intent.intent_type == IntentType.WEB_SEARCH)
    # Portability matrix: identical provider policy, host-specific effective route.
    for system_name, expected_platform in (("Windows", "windows"), ("Darwin", "macos")):
        config, router, _ = _router(ollama=True)
        with patch.dict(os.environ, {}, clear=True), patch("mary.runtime.environment.platform.system", return_value=system_name):
            snap = RuntimeEnvironment(config=config, router=router).snapshot()
            check(f"{expected_platform} host keeps Ollama first when available", snap["platform"] == expected_platform and snap["effective_conversation_route"][0] == "ollama")

        config, router, _ = _router(ollama=False)
        with patch.dict(os.environ, {}, clear=True), patch("mary.runtime.environment.platform.system", return_value=system_name):
            snap = RuntimeEnvironment(config=config, router=router).snapshot()
            check(f"{expected_platform} host safely skips Ollama when unavailable", snap["effective_conversation_route"] == ["groq", "gemini", "openrouter"])

    config, router, _ = _router(ollama=False)
    with patch.dict(os.environ, {"REPL_ID": "ambient", "CODESPACES": "true"}, clear=True):
        snap = RuntimeEnvironment(config=config, router=router).snapshot()
        check("explicit Codespaces marker beats inherited Replit marker", snap["host_type"] == "codespaces")

    check("runtime environment version is Breakthrough 12.2", RuntimeEnvironment.VERSION == "v2-breakthrough-12.2")
    check("runtime introspection remains Breakthrough 12.2 compatible", RuntimeIntrospection.VERSION in {"v2-breakthrough-12.2", "v2-breakthrough-12.3"})

    print("=" * 72)
    print("BREAKTHROUGH 12.2 VERIFIED")


if __name__ == "__main__":
    main()
