"""
MaryV2 Entry Point

Minimal interactive runtime for Mary.

This file intentionally contains very little logic.
Mary's architecture lives inside the mary/ package.
"""

from mary.core.config import Config
from mary.conversation.service import ConversationService
from mary.conversation.stage import ConversationStage
from mary.llm.router import LLMRouter
from mary.runtime.pipeline import Pipeline
from mary.runtime.state import RuntimeState


def create_mary():
    """Construct the initial Mary runtime."""

    config = Config.from_environment()

    config.ensure_directories()

    router = LLMRouter(config)

    conversation = ConversationService(
        router,
        system_prompt=(
            "You are Mary. "
            "You are a fictional character created by Unbe. "
            "Respond naturally and conversationally."
        ),
    )

    conversation_stage = ConversationStage(
        conversation,
    )

    state = RuntimeState()

    pipeline = Pipeline(
        state,
        stages=[
            conversation_stage,
        ],
        name="mary",
    )

    return pipeline


def main():
    """Run Mary's interactive terminal interface."""

    mary = create_mary()

    print()
    print("================================")
    print(" MaryV2")
    print("================================")
    print("Type 'exit' to stop.")
    print()

    while True:

        try:
            user_input = input("You: ")

        except (KeyboardInterrupt, EOFError):
            print()
            break

        user_input = user_input.strip()

        if not user_input:
            continue

        if user_input.lower() in {
            "exit",
            "quit",
        }:
            break

        try:
            result = mary.run(
                user_input
            )

            if result.success:
                print(
                    f"Mary: {result.output}"
                )
            else:
                print(
                    f"Mary encountered an error: "
                    f"{result.error}"
                )

        except Exception as exc:
            print(
                f"Mary runtime error: {exc}"
            )

        print()


if __name__ == "__main__":
    main()
