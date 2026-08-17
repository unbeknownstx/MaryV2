import pytest

from dotenv import load_dotenv

load_dotenv()

from mary.core.config import Config
from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import Pipeline, PipelineStageError
from mary.runtime.state import RuntimeState


def test_live_conversation_pipeline():
    config = Config.from_environment()

    router = LLMRouter(config)

    try:
        available = router.is_available()
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(
            f"Configured live LLM provider SDK is unavailable: {exc}"
        )

    if not available:
        pytest.skip("Configured live LLM provider is not available.")

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

    try:
        result = pipeline.run(
            "Hello Mary. This is your first live conversation."
        )
    except PipelineStageError as exc:
        # This is a live-provider integration test. A provider quota/rate-limit
        # means the external dependency is temporarily unavailable; it is not
        # a MaryV2 implementation regression. Keep all other failures hard.
        message = str(exc).lower()
        if (
            "429" in message
            or "rate limit" in message
            or "rate_limit_exceeded" in message
            or "tokens per day" in message
        ):
            pytest.skip(
                "Configured live LLM provider is temporarily rate-limited."
            )
        raise

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
