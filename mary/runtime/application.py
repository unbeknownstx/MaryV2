"""
MaryV2 - Canonical Application Runtime

Builds the complete MaryV2 application runtime used by terminal entry points.

The application runtime connects:

    Mary
      ↓
    MaryStage
      ↓
    Pipeline

It does not replace Mary's subsystem logic. Mary remains the coordinator for
identity, memory, cognition, knowledge, learning, agency, autonomy,
conversation, expression, avatar, and audio.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mary.core.mary import Mary
from mary.runtime.mary_stage import MaryStage
from mary.runtime.pipeline import Pipeline, PipelineResult
from mary.runtime.state import RuntimeState


@dataclass
class MaryApplication:
    """
    Complete application composition for one MaryV2 process.
    """

    mary: Mary
    state: RuntimeState
    pipeline: Pipeline
    memory_path: Path

    def run(
        self,
        input_text: str,
        *,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Process one input through the canonical Mary pipeline."""

        return self.pipeline.run(
            input_text,
            turn_id=turn_id,
            metadata=metadata,
        )

    def save(self) -> bool:
        """Persist Mary's durable memory."""

        return self.mary.memory.save()

    def close(self) -> bool:
        """Persist state needed when the application exits."""

        return self.save()


def create_application(
    *,
    mary: Mary | None = None,
    memory_path: str | Path | None = None,
    auto_save: bool = True,
    load_memory: bool = True,
    name: str = "mary",
) -> MaryApplication:
    """
    Construct the canonical full MaryV2 application runtime.

    Supplying an existing Mary instance is supported for tests and explicit
    dependency injection. No duplicate Mary object is created in that case.
    """

    mary = (
        mary
        if mary is not None
        else Mary()
    )

    mary.config.ensure_directories()

    resolved_memory_path = (
        Path(memory_path)
        if memory_path is not None
        else mary.config.paths.memory / "memory.json"
    )

    mary.memory.configure_persistence(
        resolved_memory_path,
        auto_save=auto_save,
        load=load_memory,
    )

    state = RuntimeState()

    stage = MaryStage(
        mary=mary,
    )

    pipeline = Pipeline(
        state,
        stages=[stage],
        name=name,
    )

    return MaryApplication(
        mary=mary,
        state=state,
        pipeline=pipeline,
        memory_path=resolved_memory_path,
    )


def run_interactive(
    application: MaryApplication | None = None,
) -> None:
    """
    Run the shared terminal interface used by every MaryV2 entry point.
    """

    print("=" * 60)
    print("MaryV2")
    print("=" * 60)

    try:
        app = (
            application
            if application is not None
            else create_application()
        )

    except Exception as exc:
        print()
        print("Mary failed to initialize.")
        print(f"{type(exc).__name__}: {exc}")
        return

    mary = app.mary

    print()
    print("Mary initialized successfully.")

    try:
        status = mary.status()

        print(
            f"Name: {status.get('name', 'Mary')}"
        )

        cognition = status.get(
            "cognition",
            {},
        )

        print(
            "LLM Provider: "
            f"{cognition.get('llm', 'unknown')}"
        )

        print(
            "LLM Model: "
            f"{cognition.get('model', 'unknown')}"
        )

    except Exception as exc:
        print(
            "Warning: Could not read full system status: "
            f"{type(exc).__name__}: {exc}"
        )

    print()
    print("Mary is ready.")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)
    print()

    try:
        while True:

            try:
                user_input = input(
                    "You: "
                ).strip()

            except (
                EOFError,
                KeyboardInterrupt,
            ):
                print()
                break

            if not user_input:
                continue

            if user_input.lower() in {
                "exit",
                "quit",
            }:
                break

            try:
                result = app.run(
                    user_input
                )

                if result.success:
                    response = result.output

                    if response is None:
                        response = (
                            "[No response was generated.]"
                        )

                    print(
                        f"Mary: {response}"
                    )

                else:
                    print(
                        "Mary encountered an error: "
                        f"{result.error}"
                    )

            except KeyboardInterrupt:
                print()
                break

            except Exception as exc:
                print()
                print(
                    "[MaryV2 Error] "
                    f"{type(exc).__name__}: {exc}"
                )
                print()

    finally:
        app.close()

    print()
    print("Mary stopped.")
