"""Verify MaryV2 Breakthrough 10: local character core + specialist task routing."""

from __future__ import annotations

import os
import tempfile

from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.turn_policy import TurnPolicyEngine


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True) -> None:
        self.name = name
        self.available = available
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(
            content="Yeah, I get what you mean. I'm here with you.",
            provider=self.name,
            model=f"fake-{self.name}",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
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


def wire(mary: Mary, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router


def main() -> None:
    print("=" * 72)
    print("MARY V2 BREAKTHROUGH 10 - LOCAL CHARACTER CORE / SPECIALIST TASK ROUTING")
    print("=" * 72)

    policy = TurnPolicyEngine()
    check(
        "messy natural personal conversation classifies local-first",
        policy.decide(input_text="idk i just wanna talk for a bit", intent=None).generation_purpose == "conversation",
    )
    check(
        "natural relationship reasoning stays local-first",
        policy.decide(input_text="what do u think im actually trying to say", intent=None).generation_purpose == "conversation",
    )
    check(
        "detached factual question classifies as task/general",
        policy.decide(input_text="what is a fish", intent=None).generation_purpose is None,
    )
    check(
        "technical coding request classifies as task/general",
        policy.decide(input_text="write me a python function to sort a list", intent=None).generation_purpose is None,
    )

    original = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="maryv2_breakthrough10_") as directory:
        os.chdir(directory)
        try:
            mary = Mary()
            router, providers = router_fixture()
            wire(mary, router)

            personal = mary.process("idk i just wanna talk for a bit")
            check(
                "top-down personal turn actually reaches Ollama first",
                personal.reasoning.metadata.get("provider") == "ollama"
                and personal.reasoning.metadata.get("turn_policy", {}).get("local_first") is True
                and providers["groq"].calls == 0,
            )

            task = mary.process("what is a fish?")
            check(
                "top-down factual turn actually reaches task/general cloud route",
                task.reasoning.metadata.get("provider") == "groq"
                and task.reasoning.metadata.get("turn_policy", {}).get("category") == "task_general",
            )

            before = sum(item.calls for item in providers.values())
            learning = mary.process(
                "please ask anything of me an i will help you as best i can you are here to learn"
            )
            after = sum(item.calls for item in providers.values())
            check(
                "explicit learning invitation uses Mary's real relationship-curiosity state with zero LLM calls",
                learning.metadata.get("conversation_learning_invitation", {}).get("handled") is True
                and after == before
                and "quirky fact" not in learning.final_response.lower(),
            )

            learned_probe = mary.relationship.learn_explicit("my test animal is a red panda")
            probe_context = mary._build_context("still just talking")
            probe_projection = str({
                "user": probe_context.get("user", {}),
                "relationship": probe_context.get("mind_state", {}).get("relationship", {}),
                "memories": probe_context.get("memory", {}).get("relevant_memories", []),
            }).lower()
            check(
                "test/probe creator residue remains durable but is absent from normal model-facing context",
                learned_probe is not None
                and "test_animal" not in probe_projection
                and "red panda" not in probe_projection,
            )

            contract = mary.system_contract.snapshot(mary)
            check(
                "bottom-up architecture contract confirms one shared model router",
                contract.get("single_llm_router") is True,
            )
            check(
                "bottom-up architecture contract confirms shared emotion state",
                contract.get("shared_emotion_state") is True,
            )
            check(
                "architecture contract preserves local conversation and cloud task routes",
                contract.get("conversation_route", [None])[0] == "ollama"
                and contract.get("task_route", [None])[0] == "groq",
            )
            check(
                "system contract has no authority wiring issues",
                mary.system_contract.validate(mary) == [],
            )

            status = mary.status()
            check(
                "runtime exposes turn policy, conversation learning, and architecture contract",
                str(status.get("turn_policy", {}).get("version", "")).startswith("v2-breakthrough-")
                and status.get("conversation_learning", {}).get("connected") is True
                and status.get("architecture_contract", {}).get("connected") is True,
            )
        finally:
            os.chdir(original)

    fallback_router, fallback = router_fixture(ollama_available=False)
    response = fallback_router.generate(
        [], purpose="conversation"
    )
    check(
        "local conversation route still degrades safely to free cloud",
        response.provider == "groq" and fallback["groq"].calls == 1,
    )

    print("=" * 72)
    print("BREAKTHROUGH 10 VERIFIED")


if __name__ == "__main__":
    main()
