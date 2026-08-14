from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse


class FakeLLM(LLMInterface):
    """Deterministic LLM used for integration tests."""

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:

        return LLMResponse(
            content="Hello from test Mary.",
            provider="fake",
            model="test-model",
            finish_reason="stop",
            usage={},
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "test-model"


def create_test_mary() -> Mary:
    mary = Mary()

    mary.llm.register_provider(
        "fake",
        FakeLLM(),
    )

    mary.config.llm.provider = "fake"

    return mary


def test_memory_can_be_recalled_by_cognition():
    mary = create_test_mary()

    mary.remember(
        "Unbe created Mary.",
        memory_type="episodic",
        importance=1.0,
    )

    memories = mary.memory.recall(
        "Who created Mary?"
    )

    assert isinstance(memories, list)


def test_memory_context_can_be_built():
    mary = create_test_mary()

    mary.remember(
        "Mary was created by Unbe.",
        memory_type="episodic",
        importance=1.0,
    )

    context = mary.memory.build_context(
        "Mary creator"
    )

    assert "relevant_memories" in context
    assert "working_memory" in context


def test_cognition_receives_memory_context():
    mary = create_test_mary()

    mary.remember(
        "Unbe is Mary's creator.",
        memory_type="episodic",
        importance=1.0,
    )

    memories = mary.memory.recall(
        "Mary creator"
    )

    result = mary.cognition.process(
        input_text="Hello Mary",
        memories=memories,
    )

    assert result.context is not None
    assert result.context.input_text == "Hello Mary"
    assert result.context.memories == memories
    assert result.reasoning.response == "Hello from test Mary."


def test_memory_manager_status():
    mary = create_test_mary()

    status = mary.memory.status()

    assert status["episodic"] is True
    assert status["semantic"] is True
    assert status["working"] is True
    assert status["retrieval"] is True
    assert status["consolidation"] is True
