from __future__ import annotations

import os
from pathlib import Path

from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.turn_policy import TurnPolicyEngine


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True, content: str | None = None) -> None:
        self.name = name
        self.available = available
        self.content = content or "Yeah, I get what you mean. I'm here with you."
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
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
        self.messages_seen: list[list] = []

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        self.messages_seen.append(list(messages))
        content = self.contents.pop(0) if self.contents else "Yeah, I'm here with you."
        return LLMResponse(
            content=content,
            provider=self.name,
            model=f"fake-{self.name}",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        )


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


def test_turn_policy_messy_personal_conversation_is_local_first():
    policy = TurnPolicyEngine()
    decision = policy.decide(
        input_text="idk i just wanna talk for a bit",
        intent=None,
    )
    assert decision.generation_purpose == "conversation"
    assert decision.local_first is True


def test_turn_policy_messy_relationship_question_is_local_first():
    policy = TurnPolicyEngine()
    decision = policy.decide(
        input_text="what do u think im actually trying to say",
        intent=None,
    )
    assert decision.category == "personal_conversation"
    assert decision.generation_purpose == "conversation"


def test_turn_policy_plain_fact_question_is_task_general():
    mary = Mary()
    intent = mary.cognition.detect_intent("what is a fish?")
    decision = mary.turn_policy.decide(
        input_text="what is a fish?",
        intent=intent,
    )
    assert decision.category == "task_general"
    assert decision.generation_purpose is None


def test_turn_policy_technical_request_is_task_general_even_if_coarse_intent_says_conversation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    text = "write me a python function to sort a list"
    intent = mary.cognition.detect_intent(text)
    decision = mary.turn_policy.decide(input_text=text, intent=intent)
    assert decision.category == "task_general"
    assert decision.generation_purpose is None


def test_real_personal_turn_uses_ollama_without_manual_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, providers = _router()
    _wire(mary, router)

    result = mary.process("idk i just wanna talk for a bit")

    assert result.reasoning.metadata["provider"] == "ollama"
    assert result.reasoning.metadata["turn_policy"]["local_first"] is True
    assert providers["groq"].calls == 0


def test_real_fact_turn_uses_task_general_cloud_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, providers = _router()
    _wire(mary, router)

    result = mary.process("what is a fish?")

    assert result.reasoning.metadata["provider"] == "groq"
    assert result.reasoning.metadata["turn_policy"]["category"] == "task_general"
    assert providers["ollama"].calls == 0


def test_explicit_private_override_still_wins_for_fact_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, providers = _router()
    _wire(mary, router)
    router.set_session_override(route="private")

    result = mary.process("what is a fish?")

    assert result.reasoning.metadata["provider"] == "ollama"
    assert providers["groq"].calls == 0


def test_local_conversation_falls_back_to_free_cloud_if_ollama_is_down(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, providers = _router(ollama_available=False)
    _wire(mary, router)

    result = mary.process("idk i just wanna talk for a bit")

    assert result.reasoning.metadata["provider"] == "groq"
    assert providers["groq"].calls >= 1


def test_explicit_learning_invitation_uses_real_relationship_gap_without_llm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, providers = _router()
    _wire(mary, router)

    result = mary.process("please ask anything of me an i will help you as best i can you are here to learn")
    lowered = result.final_response.lower()

    assert result.metadata["conversation_learning_invitation"]["handled"] is True
    assert "quirky fact" not in lowered
    assert sum(item.calls for item in providers.values()) == 0


def test_learning_invitation_asks_from_current_unresolved_gap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    # Fill four tracked categories. Values remains a real gap.
    assert mary.relationship.learn_explicit("my favorite color is blue") is not None
    assert mary.relationship.learn_explicit("i am interested in creating stories") is not None
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    assert mary.relationship.learn_explicit("i prefer you to be direct") is not None
    mary.relationship_curiosity.sync()

    response = mary.conversation_learning.respond_if_invited(
        "if u could ask me something what would u actually want to know"
    )

    assert response is not None
    assert response["category"] == "values"
    assert "what matters most to you" in response["response"].lower()


def test_creator_share_after_learning_question_still_uses_existing_relationship_learning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary.process("ask me anything")
    mary.process("i value loyalty a lot")
    profile = mary.relationship.profile()

    # This test is intentionally permissive about the generated key; the
    # existing relationship learner owns parsing/storage and must remain active.
    values = profile.get("values", [])
    assert any("loyal" in str(value).lower() for value in values)


def test_system_contract_reports_single_authoritative_router_and_local_conversation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    snapshot = mary.system_contract.snapshot(mary)

    assert snapshot["single_llm_router"] is True
    assert snapshot["shared_emotion_state"] is True
    assert snapshot["conversation_route"][0] == "ollama"
    assert snapshot["task_route"][0] == "groq"
    assert mary.system_contract.validate(mary) == []


def test_status_exposes_turn_policy_learning_bridge_and_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    status = mary.status()

    assert status["turn_policy"]["version"].startswith("v2-breakthrough-")
    assert status["conversation_learning"]["connected"] is True
    assert status["architecture_contract"]["connected"] is True


def test_turn_metadata_records_policy_category_for_debug_truth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, _ = _router()
    _wire(mary, router)

    result = mary.process("what do u think about how im building you")

    policy = result.reasoning.metadata["turn_policy"]
    assert policy["category"] == "personal_conversation"
    assert policy["generation_purpose"] == "conversation"


def test_paid_openai_is_never_selected_by_turn_policy():
    policy = TurnPolicyEngine()
    for text in (
        "idk i just wanna talk",
        "what is a fish",
        "write me a python function",
        "what do u think about me",
    ):
        decision = policy.decide(input_text=text, intent=None)
        assert decision.generation_purpose in {None, "conversation"}
        assert "openai" not in decision.rationale.lower()


def test_root_run_mary_is_only_a_canonical_launcher_shim():
    source = Path("run_mary.py").read_text(encoding="utf-8")
    assert "from scripts.run_mary import main" in source
    assert "Mary(" not in source
    assert "run_interactive" not in source


def test_bad_local_improvisation_is_revised_locally_without_cloud_leak(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router, providers = _router()
    ollama = SequenceProvider(
        "ollama",
        [
            "I've been noodling on a red panda sketch lately. I miss the rain.",
            "Nothing dramatic is pulling at me right now. I'm happy to just sit here and talk with you.",
        ],
    )
    router.register_provider("ollama", ollama)
    _wire(mary, router)

    result = mary.process("idk i just wanna talk for a bit")

    assert result.reflection.decision.value == "revise"
    assert "red panda" not in result.final_response.lower()
    assert "miss the rain" not in result.final_response.lower()
    assert ollama.calls == 2
    assert providers["groq"].calls == 0


def test_probe_creator_record_does_not_enter_normal_model_projection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    learned = mary.relationship.learn_explicit("my test animal is a red panda")
    assert learned is not None

    router, providers = _router()
    ollama = SequenceProvider("ollama", ["Yeah, I'm here. What's on your mind?"])
    router.register_provider("ollama", ollama)
    _wire(mary, router)

    mary.process("idk i just wanna talk for a bit")

    combined = "\n".join(
        str(message.content)
        for call in ollama.messages_seen
        for message in call
    ).lower()
    assert "test animal" not in combined
    assert "red panda" not in combined
