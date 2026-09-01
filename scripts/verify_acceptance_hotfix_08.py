"""Verify V2 acceptance Hotfix 08: capability truth + conversational repair."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import IntentType
from mary.cognition.reasoning import ReasoningResult
from mary.core.config import Config
from mary.expression.emotion import Emotion
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.application import create_application


class FakeProvider(LLMInterface):
    def __init__(self, name: str, content: str | None = None) -> None:
        self.name = name
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
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return f"fake-{self.name}"


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def router_fixture() -> tuple[LLMRouter, dict[str, FakeProvider]]:
    config = Config()
    config.llm.provider = "groq"
    config.llm.routing_strategy = "free_first"
    config.llm.free_provider_order = ["groq", "gemini", "openrouter", "ollama"]
    router = LLMRouter(config)
    providers = {name: FakeProvider(name) for name in ("groq", "gemini", "openrouter", "ollama", "openai")}
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def wire_router(mary, router: LLMRouter) -> None:
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
    print("MARY V2 ACCEPTANCE HOTFIX 08 - CAPABILITY TRUTH + REPAIR")
    print("=" * 72)

    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="maryv2_hotfix08_") as directory:
        os.chdir(directory)
        app = None
        paid_app = None
        try:
            app = create_application(
                memory_path=Path(directory) / "data" / "memory" / "memory.json",
                auto_save=False, load_memory=False, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            mary = app.mary
            intent = mary.cognition.detect_intent("go ahead and use ollama my local llm")
            check("natural Ollama command selects process-local model control", intent.intent_type == IntentType.TOOL_USE and intent.parameters.get("operation") == "set_session")

            router, providers = router_fixture()
            providers["ollama"].content = "A fish is an aquatic vertebrate that typically breathes through gills."
            wire_router(mary, router)
            control = _turn(app, "go ahead and use ollama my local llm")
            answer = _turn(app, "what is a fish?")
            check("route control becomes active without roleplaying a call", "Local-only generation is active" in control.final_response)
            check("next real generated turn actually uses Ollama", answer.reasoning.metadata.get("provider") == "ollama" and providers["groq"].calls == 0)

            status_intent = mary._detect_intent("you are using it arent you")
            check("pronoun route-status follow-up stays deterministic", status_intent.intent_type == IntentType.SELF_QUERY and status_intent.parameters.get("self_query_type") == "runtime_architecture")

            router.clear_session_override()
            response = router.generate([LLMMessage(role="user", content="route reset")])
            check("clearing temporary override restores free-first", response.provider == "groq")

            context = CognitiveContext(input_text="are you using ollama?")
            issues = mary.reflection._provider_action_truth_audit(
                context,
                ReasoningResult(response="Yeah, I'm on the local LLM now—no cloud detour.", metadata={"provider": "groq"}),
            )
            check("false provider-use claims are rejected", bool(issues))

            mind_issues = mary.reflection._unsupported_creator_mindreading_audit(
                CognitiveContext(input_text="hmm maybe but i dont agree"),
                "You're sidestepping the real issue. That feels like hiding.",
            )
            check("simple disagreement cannot be reframed as hidden motives", bool(mind_issues))

            repair = mary.continuity.build(
                input_text="thats not really what i meant",
                intent_type=IntentType.CONVERSATION,
                recent_conversation=[{"role": "assistant", "content": "Maybe it's interface lag."}],
            )
            check("correction drops the prior hypothesis and selects reflect", repair.drive.value == "reflect" and any("Drop the prior hypothesis" in item for item in repair.instructions))

            appraisal = mary.emotion_appraiser.appraise(
                input_text="hmm maybe but i dont agree",
                response_text="",
                intent=mary.cognition.detect_intent("hmm maybe but i dont agree"),
            )
            check("disagreement produces attentive curiosity instead of defensiveness", appraisal.emotion == Emotion.CURIOSITY and appraisal.relationship_relevance >= 0.9)

            paid_app = create_application(
                memory_path=Path(directory) / "paid_data" / "memory" / "memory.json",
                auto_save=False, load_memory=False, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            paid_mary = paid_app.mary
            paid_router, paid_providers = router_fixture()
            paid_providers["openai"].content = "Expert: separate subjective language from verified capability use."
            paid_providers["groq"].content = "Yeah. I can go deeper while still being exact about what my runtime actually did."
            wire_router(paid_mary, paid_router)
            paid_result = _turn(paid_app, "go ahead and call open ai and think bigger about this interaction")
            check("explicit OpenAI request performs exactly one paid expert call", paid_providers["openai"].calls == 1 and paid_router.resource_governor.paid_calls == 1)
            check("Mary records paid expert provenance while synthesizing as herself", paid_result.reasoning.metadata.get("expert_consultation", {}).get("provider") == "openai" and paid_result.reasoning.metadata.get("provider") == "groq")

            try:
                paid_router.set_session_override(provider="openai")
            except ValueError:
                sticky_blocked = True
            else:
                sticky_blocked = False
            check("paid OpenAI cannot become a sticky session route", sticky_blocked)

            feeling = paid_mary.self_introspection.build("relationship_feelings", query="what do u feel when we talk")
            fallback = str(feeling.get("fallback_response", "")).lower()
            check("neutral emotion meter still exposes grounded relational attentiveness", "steady" in fallback and "care" in fallback)
        finally:
            if paid_app is not None:
                paid_app.close()
            if app is not None:
                app.close()
            os.chdir(original)

    print("=" * 72)
    print("ACCEPTANCE HOTFIX 08 VERIFIED")


if __name__ == "__main__":
    main()
