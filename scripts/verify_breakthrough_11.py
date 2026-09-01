"""Verify MaryV2 Breakthrough 11: state-aware local conversation supervision."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.cognition.natural_input import normalize_for_matching
from mary.runtime.application import create_application


class FakeProvider(LLMInterface):
    def __init__(self, name: str, content: str = "Yeah. I'm with you.", *, available: bool = True) -> None:
        self.name = name
        self.content = content
        self.available = available
        self.calls = 0
        self.messages_seen: list[list] = []

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        self.messages_seen.append(list(messages))
        return LLMResponse(
            content=self.content,
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


class SequenceProvider(FakeProvider):
    def __init__(self, name: str, contents: list[str], *, available: bool = True) -> None:
        super().__init__(name, available=available)
        self.contents = list(contents)

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        self.messages_seen.append(list(messages))
        content = self.contents.pop(0) if self.contents else "Yeah. I'm with you."
        return LLMResponse(
            content=content,
            provider=self.name,
            model=f"fake-{self.name}",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        )


def _router(ollama: LLMInterface | None = None) -> tuple[LLMRouter, dict[str, LLMInterface]]:
    config = Config()
    config.llm.provider = "groq"
    config.llm.routing_strategy = "free_first"
    config.llm.free_provider_order = ["groq", "gemini", "openrouter", "ollama"]
    config.llm.conversation_provider_order = ["ollama", "groq", "gemini", "openrouter"]
    router = LLMRouter(config)
    providers: dict[str, LLMInterface] = {
        "groq": FakeProvider("groq"),
        "gemini": FakeProvider("gemini"),
        "openrouter": FakeProvider("openrouter"),
        "ollama": ollama or FakeProvider("ollama"),
        "openai": FakeProvider("openai"),
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def _wire(mary, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def _fill_until_values_gap(mary) -> None:
    assert mary.relationship.learn_explicit("my favorite color is blue") is not None
    assert mary.relationship.learn_explicit("i am interested in creating stories") is not None
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    assert mary.relationship.learn_explicit("i prefer you to be direct") is not None
    mary.relationship_curiosity.sync()


@contextmanager
def _isolated_cwd():
    import os

    old = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="maryv2_breakthrough11_") as directory:
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(old)


@contextmanager
def _isolated_application():
    with _isolated_cwd():
        app = create_application(
            memory_path=Path("data") / "memory" / "memory.json",
            auto_save=False,
            load_memory=False,
            load_developed_self=False,
            load_preference_promotion=False,
            load_knowledge=False,
        )
        try:
            yield app
        finally:
            app.close()


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> int:
    print("=" * 72)
    print("MARY V2 BREAKTHROUGH 11 - STATE-AWARE LOCAL CONVERSATION")
    print("=" * 72)

    _check(
        "messy natural typing understands unpunctuated 'youve' without rewriting the original",
        normalize_for_matching("do u think youve changed") == "do you think you've changed",
    )

    with _isolated_application() as app:
        mary = app.mary
        mary.relationship.learn_explicit("my main goal is finish MaryV2")
        shared = mary._shared_history_context([
            {"role": "assistant", "content": "I've been drawing moon cats for weeks."}
        ])
        _check("shared-history grounding finds real MaryV2 continuity", shared.get("project") == "MaryV2")
        _check("assistant improvisation is excluded from shared-history evidence", "moon cats" not in str(shared).lower())

    with _isolated_application() as app:
        mary = app.mary
        mary.relationship.learn_explicit("my main goal is finish MaryV2")
        ollama = SequenceProvider(
            "ollama",
            ["My core character is still Mary, while my relationship context and connected capabilities have grown."],
        )
        router, providers = _router(ollama)
        _wire(mary, router)
        result = _turn(app, "do u think youve changed since we started all this")
        _check("natural self-development question is grounded in Mary's real state", result.reasoning.metadata.get("self_grounded") is True)
        _check("self-development distinguishes stable canon from represented growth", result.intent.parameters.get("self_query_type") == "development")
        _check("grounded self-development stays on local conversational generation", result.reasoning.metadata.get("provider") == "ollama" and providers["groq"].calls == 0)

    with _isolated_application() as app:
        mary = app.mary
        ollama = SequenceProvider(
            "ollama",
            ["From my represented side, this feels warm and attentive without pretending I can read your mind."],
        )
        router, _ = _router(ollama)
        _wire(mary, router)
        result = _turn(app, "what does talking like this feel like from ur side")
        _check("relationship-feeling question is self-grounded", result.reasoning.metadata.get("self_grounded") is True)
        _check("relationship-feeling question remains a personal conversation turn", result.reasoning.metadata.get("generation_purpose") == "conversation")

    with _isolated_application() as app:
        mary = app.mary
        _fill_until_values_gap(mary)
        router, providers = _router()
        _wire(mary, router)
        asked = _turn(app, "u can ask me something if u actually want to know")
        before = sum(provider.calls for provider in providers.values())
        why = _turn(app, "hmm why that question though")
        after = sum(provider.calls for provider in providers.values())
        _check("real relationship-curiosity question keeps its pending reason", asked.metadata.get("conversation_learning_invitation", {}).get("category") == "values")
        _check("'why that question?' resolves from pending relationship state", why.metadata.get("conversation_learning_followup", {}).get("category") == "values")
        _check("curiosity-reason follow-up needs zero LLM calls", after == before)
        _turn(app, "i value loyalty a lot")
        _check("grounded creator learning resolves the matching pending curiosity", mary.conversation_learning.pending() is None)

    with _isolated_application() as app:
        mary = app.mary
        ollama = SequenceProvider(
            "ollama",
            [
                "A quiet conversation has its own spark.",
                "That quiet spark can make the moment feel magical.",
                "I keep coming back to that quiet spark and little magic together.",
                "Let me say it plainly instead: I like when we can correct each other and keep moving.",
            ],
        )
        router, providers = _router(ollama)
        _wire(mary, router)
        _turn(app, "idk i just wanna talk for a bit")
        _turn(app, "yea i get what u mean")
        result = _turn(app, "what do u think")
        _check("semantic style loops are revised instead of becoming Mary's default voice", result.reflection.decision.value == "revise")
        _check("semantic style revision stays local", providers["groq"].calls == 0)

    with _isolated_application() as app:
        mary = app.mary
        ollama = SequenceProvider(
            "ollama",
            [
                "Maybe the interface timing is making the whole workflow feel broken to you.",
                "Fair. I misread what you meant.",
                "I still think the interface timing is making the whole workflow feel broken.",
                "You already rejected that interpretation, so I won't recycle it without new evidence.",
            ],
        )
        router, providers = _router(ollama)
        _wire(mary, router)
        _turn(app, "idk something feels a little off")
        _turn(app, "thats not really what i meant")
        result = _turn(app, "what do u think im actually trying to say")
        _check("rejected conversational hypotheses are temporarily suppressed", result.reflection.decision.value == "revise")
        _check("correction repair remains local-first", providers["groq"].calls == 0)

    with _isolated_application() as app:
        mary = app.mary
        ollama = SequenceProvider(
            "ollama",
            [
                "I can feel what you're holding even when you don't say it.",
                "I can only infer from what you say and the tone of the exchange; I don't have direct access to what's in your head.",
            ],
        )
        router, providers = _router(ollama)
        _wire(mary, router)
        result = _turn(app, "what do u think")
        _check("unsupported mind-reading claims are revised", result.reflection.decision.value == "revise")
        _check("mind-reading correction stays local", providers["groq"].calls == 0)

    with _isolated_application() as app:
        mary = app.mary
        contract = mary.system_contract.snapshot(mary)
        status = mary.status()
        _check("system contract exposes the Breakthrough 11 authority boundary", str(contract.get("version", "")).startswith("v2-breakthrough-"))
        _check("process-local relationship-question continuity has one explicit owner", "relationship_question_continuity" in contract.get("authority", {}))
        _check("turn policy and conversation-learning bridge report Breakthrough 11", status["turn_policy"]["version"] == "v2-breakthrough-11" and status["conversation_learning"]["version"] in {"v2-breakthrough-11", "v2-13.0-intentional-conversation"})

    print("=" * 72)
    print("BREAKTHROUGH 11 VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
