from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import PipelineContext
from mary.runtime.state import RuntimeState
from mary.core.config import Config


class FakeLLM(LLMInterface):
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:

        return LLMResponse(
            content="Hello. I am Mary.",
            provider="fake",
            model="test-model",
            usage={
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "test-model"


def test_conversation_service():
    config = Config()

    router = LLMRouter(config)

    fake = FakeLLM()

    router.register_provider(
        "fake",
        fake,
    )

    service = ConversationService(
        router,
        system_prompt="You are Mary.",
    )

    response = service.respond(
        "Hello Mary.",
        provider="fake",
    )

    assert response.content == "Hello. I am Mary."
    assert response.provider == "fake"
    assert response.model == "test-model"


def test_conversation_stage():
    config = Config()

    router = LLMRouter(config)

    router.register_provider(
        "fake",
        FakeLLM(),
    )

    service = ConversationService(
        router,
        system_prompt="You are Mary.",
    )

    stage = ConversationStage(
        service,
        provider="fake",
    )

    state = RuntimeState()

    context = PipelineContext(
        runtime_state=state,
        turn_id="test-turn",
        input_data="Hello Mary.",
    )

    result = stage.process(
        context
    )

    assert result.success
    assert result.output == "Hello. I am Mary."

    assert result.values[
        "llm_response"
    ].provider == "fake"

    assert result.metadata[
        "llm_provider"
    ] == "fake"
