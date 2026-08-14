from mary.core.config import Config
from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import Pipeline
from mary.runtime.state import RuntimeState


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
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "test-model"


def test_full_conversation_pipeline():

    config = Config()

    router = LLMRouter(config)

    router.register_provider(
        "fake",
        FakeLLM(),
    )

    conversation = ConversationService(
        router,
        system_prompt="You are Mary.",
    )

    stage = ConversationStage(
        conversation,
        provider="fake",
    )

    state = RuntimeState()

    pipeline = Pipeline(
        state,
        stages=[
            stage,
        ],
    )

    result = pipeline.run(
        "Hello Mary.",
    )

    assert result.success
    assert result.output == "Hello. I am Mary."

    assert result.stage_results[0].status == "completed"

    assert state.turn_count == 1
