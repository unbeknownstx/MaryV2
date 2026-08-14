from dotenv import load_dotenv

load_dotenv()

from mary.core.config import Config
from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import Pipeline
from mary.runtime.state import RuntimeState


def test_live_conversation_pipeline():
    config = Config.from_environment()

    router = LLMRouter(config)

    assert router.is_available(), (
        "Configured LLM provider is not available."
    )

    conversation = ConversationService(
        router,
        system_prompt=(
            "You are Mary. "
            "Respond naturally, warmly, and briefly."
        ),
    )

    stage = ConversationStage(
        conversation,
        provider=config.llm.provider,
    )

    state = RuntimeState()

    pipeline = Pipeline(
        state,
        stages=[stage],
        name="mary_conversation",
    )

    result = pipeline.run(
        "Hello Mary. This is your first live conversation."
    )

    assert result.success
    assert result.output
    assert isinstance(result.output, str)

    print("\n--- MARY ---")
    print(result.output)

    print("\n--- PIPELINE ---")
    print("Status:", result.status.value)
    print("Turn:", result.turn_id)
    print("Elapsed:", result.elapsed)


if __name__ == "__main__":
    test_live_conversation_pipeline()
