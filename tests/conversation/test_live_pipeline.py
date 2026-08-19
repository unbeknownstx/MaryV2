from __future__ import annotations

import os

import pytest

from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.core.config import Config
from mary.llm.interface import LLMProviderError
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import Pipeline, PipelineStageError
from mary.runtime.state import RuntimeState


RUN_LIVE_TESTS = (
    os.getenv(
        "MARY_RUN_LIVE_TESTS",
        "",
    ).strip()
    == "1"
)


@pytest.mark.skipif(
    not RUN_LIVE_TESTS,
    reason=(
        "Live LLM test disabled. "
        "Set MARY_RUN_LIVE_TESTS=1 to run it."
    ),
)
def test_live_conversation_pipeline():
    """
    Explicit live smoke test for Mary's conversation pipeline.

    This test makes a real external model request and is therefore
    disabled during the normal deterministic/offline test suite.

    Set:

        MARY_RUN_LIVE_TESTS=1

    to run it intentionally.

    LLMRouter chooses Mary's active adaptive route:

        Groq -> Gemini -> OpenRouter -> Ollama

    External-provider outages, quotas, and timeouts skip this live
    smoke test. Non-provider pipeline failures still fail normally.
    """

    config = Config.from_environment()
    router = LLMRouter(config)

    try:
        available = router.is_available()
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(
            "Configured live LLM provider SDK "
            f"is unavailable: {exc}"
        )

    if not available:
        pytest.skip(
            "No configured live LLM route "
            "is currently available."
        )

    conversation = ConversationService(
        router,
        system_prompt=(
            "You are Mary. "
            "Respond naturally, warmly, and briefly."
        ),
    )

    # provider=None lets Mary's adaptive router choose the route.
    # Do not pin this test to config.llm.provider.
    stage = ConversationStage(
        conversation,
        provider=None,
    )

    state = RuntimeState()

    pipeline = Pipeline(
        state,
        stages=[stage],
        name="mary_conversation",
    )

    try:
        result = pipeline.run(
            "Hello Mary. "
            "This is your first live conversation."
        )
    except PipelineStageError as exc:
        cause = exc.__cause__

        if isinstance(
            cause,
            LLMProviderError,
        ):
            pytest.skip(
                "Live LLM route is temporarily "
                f"unavailable: {cause}"
            )

        raise

    assert result is not None
    assert result.output

    assert (
        getattr(
            result.status,
            "value",
            str(result.status),
        )
        == "completed"
    )