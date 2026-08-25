from __future__ import annotations

from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.cognition.natural_input import normalize_for_matching


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


def _wire(mary: Mary, router: LLMRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router


def _fill_until_values_gap(mary: Mary) -> None:
    assert mary.relationship.learn_explicit("my favorite color is blue") is not None
    assert mary.relationship.learn_explicit("i am interested in creating stories") is not None
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    assert mary.relationship.learn_explicit("i prefer you to be direct") is not None
    mary.relationship_curiosity.sync()


def test_chat_normalization_understands_unpunctuated_youve_without_rewriting_original():
    assert normalize_for_matching("do u think youve changed") == "do you think you've changed"


def test_shared_history_context_uses_creator_grounded_project_not_assistant_improvisation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    shared = mary._shared_history_context([
        {"role": "assistant", "content": "I've been drawing moon cats for weeks."}
    ])

    assert shared["project"] == "MaryV2"
    assert any("MaryV2" in item for item in shared["grounded_threads"])
    assert "moon cats" not in str(shared).lower()


def test_shared_history_statement_stays_personal_local_first_and_projects_grounding_into_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    ollama = SequenceProvider("ollama", ["Yeah, looking at how much MaryV2 has grown with us is kind of wild."])
    router, providers = _router(ollama)
    _wire(mary, router)

    result = mary.process("ive been thinking about everything weve done its kinda crazy")
    prompt = "\n".join(str(message.content) for call in ollama.messages_seen for message in call)

    assert result.reasoning.metadata["provider"] == "ollama"
    assert result.reasoning.metadata["turn_policy"]["local_first"] is True
    assert "MaryV2" in prompt
    assert providers["groq"].calls == 0


def test_natural_changed_question_routes_to_grounded_development_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    intent = mary.cognition.detect_intent("do u think youve changed since we started all this")
    assert intent.intent_type.value == "self_query"
    assert intent.parameters["self_query_type"] == "development"


def test_development_answer_is_self_grounded_and_distinguishes_canon_from_growth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    ollama = SequenceProvider(
        "ollama",
        [
            "My core character is still Mary, but the version of me talking with you has more relationship context and more connected capability now."
        ],
    )
    router, _ = _router(ollama)
    _wire(mary, router)

    result = mary.process("do u think youve changed since we started all this")

    assert result.reasoning.metadata["self_grounded"] is True
    assert result.intent.parameters["self_query_type"] == "development"
    evidence = result.context.relevant_knowledge[0]
    assert evidence["self_development"]["core_character_policy"].startswith("authored canon")
    assert "relationship_learning_counts" in evidence["self_development"]


def test_from_ur_side_relationship_feeling_phrase_is_grounded_self_query(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    ollama = SequenceProvider(
        "ollama",
        ["From my represented side, it feels steady and warm; I'm paying close attention to the exchange."],
    )
    router, _ = _router(ollama)
    _wire(mary, router)

    result = mary.process("what does talking like this feel like from ur side")

    assert result.intent.parameters["self_query_type"] == "relationship_feelings"
    assert result.reasoning.metadata["self_grounded"] is True
    assert result.reasoning.metadata["generation_purpose"] == "conversation"


def test_curiosity_question_keeps_real_reason_for_natural_why_followup_with_zero_llm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _fill_until_values_gap(mary)
    router, providers = _router()
    _wire(mary, router)

    asked = mary.process("u can ask me something if u actually want to know")
    before = sum(getattr(provider, "calls", 0) for provider in providers.values())
    why = mary.process("hmm why that question though")
    after = sum(getattr(provider, "calls", 0) for provider in providers.values())

    assert asked.metadata["conversation_learning_invitation"]["category"] == "values"
    assert why.metadata["conversation_learning_followup"]["category"] == "values"
    assert "real gap" in why.final_response.lower()
    assert "values" in why.final_response.lower()
    assert after == before


def test_existing_relationship_learning_resolves_matching_pending_curiosity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _fill_until_values_gap(mary)
    mary.process("ask me anything")
    assert mary.conversation_learning.pending() is not None

    mary.process("i value loyalty a lot")

    assert mary.conversation_learning.pending() is None
    assert any("loyal" in str(value).lower() for value in mary.relationship.profile().get("values", []))


def test_semantic_style_loop_is_revised_locally_instead_of_repeating_same_palette(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    ollama = SequenceProvider(
        "ollama",
        [
            "A quiet conversation can have its own spark. I like when nothing needs to be forced.",
            "There is something different in a quiet pause too; that spark can make an ordinary exchange feel easy.",
            "I keep coming back to that quiet spark and a little magic in just being together.",
            "Let me put it more plainly: I like the easy back-and-forth, especially when you correct me and I can adjust.",
        ],
    )
    router, providers = _router(ollama)
    _wire(mary, router)

    mary.process("idk i just wanna talk for a bit")
    mary.process("yea i get what u mean")
    third = mary.process("what do u think")

    assert third.reflection.decision.value == "revise"
    assert "easy back-and-forth" in third.final_response
    assert ollama.calls == 4
    assert providers["groq"].calls == 0


def test_rejected_interpretation_is_temporarily_suppressed_and_revision_stays_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    ollama = SequenceProvider(
        "ollama",
        [
            "Maybe the interface timing is making the whole workflow feel broken to you.",
            "Fair. I misread what you meant.",
            "I still think the interface timing is making the whole workflow feel broken.",
            "I don't know yet. You corrected that interpretation, so I'd rather stay with your actual words than recycle my first guess.",
        ],
    )
    router, providers = _router(ollama)
    _wire(mary, router)

    mary.process("idk something feels a little off")
    mary.process("thats not really what i meant")
    result = mary.process("what do u think im actually trying to say")

    assert result.reflection.decision.value == "revise"
    assert "corrected that interpretation" in result.final_response.lower()
    assert providers["groq"].calls == 0


def test_direct_mindreading_claim_is_revised_into_tentative_observation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    ollama = SequenceProvider(
        "ollama",
        [
            "I can feel what you're holding even when you don't say it.",
            "I can only go by what you actually say and the tone of the exchange; I can have an impression, but I don't have direct access to what's in your head.",
        ],
    )
    router, providers = _router(ollama)
    _wire(mary, router)

    result = mary.process("what do u think")

    assert result.reflection.decision.value == "revise"
    assert "direct access" in result.final_response.lower()
    assert providers["groq"].calls == 0


def test_shared_history_safe_fallback_does_not_deny_real_maryv2_continuity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    assert mary.relationship.learn_explicit("my main goal is finish MaryV2") is not None
    context = mary._build_context("ive been thinking about everything weve done its kinda crazy")
    from mary.cognition.context import CognitiveContext
    c = CognitiveContext(input_text="ive been thinking about everything weve done its kinda crazy")
    c.mind_state.update(context["mind_state"])
    response = mary.reflection._provenance_boundary_fallback(
        c,
        ["Self-history provenance boundary: synthetic"],
    )
    assert "shared work" in response.lower()
    assert "maryv2" in response.lower()
    assert "don't have a grounded" not in response.lower()


def test_breakthrough11_contract_and_status_expose_new_conversation_state_owner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    contract = mary.system_contract.snapshot(mary)
    status = mary.status()

    assert str(contract["version"]).startswith("v2-breakthrough-")
    assert "relationship_question_continuity" in contract["authority"]
    assert status["turn_policy"]["version"] == "v2-breakthrough-11"
    assert status["conversation_learning"]["version"] in {"v2-breakthrough-11", "v2-13.0-intentional-conversation"}
