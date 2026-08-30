"""Deterministic verification for Breakthrough 12 host/capability portability."""

from __future__ import annotations

import os
from unittest.mock import patch

from mary.core.config import Config
from mary.core.mary import Mary
from mary.cognition.intent import IntentType
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.environment import RuntimeEnvironment


class FakeProvider(LLMInterface):
    def __init__(self, name: str, available: bool = True):
        self.name = name
        self.available = available
        self.calls = 0
    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(f"{self.name} answer", self.name, f"{self.name}-test", "stop")
    def is_available(self): return self.available
    def provider_name(self): return self.name
    def model_name(self): return "qwen3:4b-instruct" if self.name == "ollama" else f"{self.name}-test"


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 BREAKTHROUGH 12 - HOST AWARENESS / DYNAMIC CAPABILITIES")
    print("=" * 72)

    config = Config()
    router = LLMRouter(config)
    providers = {
        "ollama": FakeProvider("ollama", False),
        "groq": FakeProvider("groq"),
        "gemini": FakeProvider("gemini"),
        "openrouter": FakeProvider("openrouter"),
        "openai": FakeProvider("openai"),
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)

    with patch.dict(os.environ, {"REPL_ID": "verification-repl"}, clear=False):
        env = RuntimeEnvironment(config=config, router=router)
        snap = env.snapshot()
        check("Replit host is detected without changing Mary's core", snap["host_type"] == "replit")
        check("preferred conversation policy still includes optional Ollama", snap["conversation_policy"][0] == "ollama")
        check("effective Replit conversation route skips unavailable Ollama", snap["effective_conversation_route"] == ["groq", "gemini", "openrouter"])
        check("task/general route remains available through configured cloud providers", snap["effective_task_route"][:3] == ["groq", "gemini", "openrouter"])

        mary = Mary()
        mary.llm = router
        mary.reasoning.llm = router
        mary.reflection.llm = router
        mary.conversation.router = router
        mary.runtime_environment = env

        intent = mary.cognition.detect_intent("what models can u use right now?")
        check("current model availability is runtime introspection, never web search", intent.intent_type == IntentType.SELF_QUERY)
        intent = mary.cognition.detect_intent("does anything change because were not on my pc?")
        check("host-change question is grounded runtime introspection", intent.intent_type == IntentType.SELF_QUERY)
        intent = mary.cognition.detect_intent("idk im working on u from replit on my phone right now what do u think about that?")
        check("personal Replit conversation containing right-now does not become web search", intent.intent_type != IntentType.WEB_SEARCH)
        intent = mary.cognition.detect_intent("what is the latest Python release?")
        check("real current external information still routes to web", intent.intent_type == IntentType.WEB_SEARCH)

        response = mary._runtime_architecture_response(query="what models can u use right now?").lower()
        check("runtime answer names the current host", "replit" in response)
        check("runtime answer truthfully reports Ollama unavailable", "ollama is not reachable" in response)
        check("runtime answer exposes effective cloud fallback", "groq -> gemini -> openrouter" in response)

        result = mary.process("idk i just wanna talk for a bit")
        check("real conversational generation continues through available provider", result.reasoning.metadata.get("provider") == "groq")
        check("unavailable Ollama is not asked to generate", providers["ollama"].calls == 0)

    print("=" * 72)
    print("BREAKTHROUGH 12 VERIFIED")


if __name__ == "__main__":
    main()
