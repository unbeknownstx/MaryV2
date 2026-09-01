"""Verify V2 Acceptance Hotfix 09: local-first character conversation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mary.cognition.intent import IntentType
from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.application import create_application


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True) -> None:
        self.name = name
        self.available = available
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(
            content=f"{self.name} response",
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


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def router_fixture(*, ollama_available: bool = True):
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


def wire(mary, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def main() -> None:
    print("=" * 72)
    print("MARY V2 ACCEPTANCE HOTFIX 09 - LOCAL-FIRST CHARACTER CONVERSATION")
    print("=" * 72)

    router, providers = router_fixture()
    check(
        "ordinary conversation route prefers Ollama locally",
        router._provider_order(None, purpose="conversation")[0] == "ollama",
    )
    check(
        "task/general route remains cloud free-first",
        router._provider_order(None)[0] == "groq",
    )
    conversation = router.generate(
        [LLMMessage(role="user", content="just talk with me")],
        purpose="conversation",
    )
    check(
        "conversation purpose actually executes through Ollama",
        conversation.provider == "ollama" and providers["groq"].calls == 0,
    )

    fallback_router, fallback = router_fixture(ollama_available=False)
    fallback_result = fallback_router.generate(
        [LLMMessage(role="user", content="just talk with me")],
        purpose="conversation",
    )
    check(
        "conversation safely falls back to free cloud when local Ollama is unavailable",
        fallback_result.provider == "groq" and fallback["groq"].calls == 1,
    )

    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="maryv2_hotfix09_") as directory:
        os.chdir(directory)
        app = None
        try:
            app = create_application(
                memory_path=Path(directory) / "data" / "memory" / "memory.json",
                auto_save=False, load_memory=False, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            mary = app.mary
            intent = mary.cognition.detect_intent("go into ollama llm")
            check(
                "natural 'go into ollama llm' phrasing is recognized",
                intent.intent_type == IntentType.TOOL_USE
                and intent.parameters.get("operation") == "set_session",
            )

            capability = mary.cognition.detect_intent("how can i let you use ollama?")
            check(
                "Ollama setup question resolves from Mary's runtime instead of provider improvisation",
                capability.intent_type == IntentType.SELF_QUERY
                and capability.parameters.get("self_query_type") == "runtime_architecture",
            )

            real_router, real_providers = router_fixture()
            wire(mary, real_router)
            result = _turn(app, "idk i just wanna talk for a bit")
            check(
                "Mary ordinary conversation automatically uses local-first purpose",
                result.reasoning.metadata.get("generation_purpose") == "conversation"
                and result.reasoning.metadata.get("provider") == "ollama",
            )

            real_router.set_session_override(provider="gemini")
            overridden = _turn(app, "still just talking")
            check(
                "explicit temporary provider override still beats conversation default",
                overridden.reasoning.metadata.get("provider") == "gemini",
            )

            status = mary.status().get("cognition", {})
            check(
                "runtime status exposes separate conversation and task routes",
                status.get("conversation_provider_order", [None])[0] == "ollama"
                and status.get("provider_order", [None])[0] == "groq",
            )
        finally:
            if app is not None:
                app.close()
            os.chdir(original)

    print("=" * 72)
    print("ACCEPTANCE HOTFIX 09 VERIFIED")


if __name__ == "__main__":
    main()
