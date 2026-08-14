"""
MaryV2 Interactive Runtime

Provides a simple terminal interface for talking to Mary
through the existing runtime pipeline.
"""

from __future__ import annotations

from dotenv import load_dotenv

from mary.core.config import Config
from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import Pipeline
from mary.runtime.state import RuntimeState


def create_mary() -> Pipeline:
    """Create a live Mary conversation pipeline."""

    load_dotenv()

    config = Config.from_environment()

    router = LLMRouter(config)

    conversation = ConversationService(
        router,
        system_prompt=(
            "You are Mary. "
            "You are warm, kind, curious, funny, and natural. "
            "Respond as a conversational character. "
            "Do not claim to have experiences or memories "
            "that have not been provided to you."
        ),
    )

    stage = ConversationStage(
        conversation,
        provider=config.llm.provider,
    )

    state = RuntimeState()

    return Pipeline(
        state,
        stages=[stage],
        name="mary_interactive",
    )


def main() -> None:
    """Start an interactive Mary session."""

    pipeline = create_mary()

    print()
    print("========================================")
    print("             MARY V2")
    print("========================================")
    print("Mary is online.")
    print("Type 'exit' or 'quit' to end the session.")
    print()

    while True:

        try:
            user_input = input("You: ").strip()

        except (KeyboardInterrupt, EOFError):
            print("\n\nMary session ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in {
            "exit",
            "quit",
        }:
            print("\nMary session ended.")
            break

        try:
            result = pipeline.run(
                user_input
            )

            print()
            print("Mary:", result.output)
            print()

        except Exception as exc:
            print()
            print(
                "Mary encountered an error:",
                exc,
            )
            print()


if __name__ == "__main__":
    main()
