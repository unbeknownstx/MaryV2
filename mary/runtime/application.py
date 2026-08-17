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




# ================================================================
# INTERACTIVE TERMINAL UX
# ================================================================


_POWERSHELL_PREFIXES = (
    "test-path ",
    "get-content ",
    "set-content ",
    "add-content ",
    "remove-item ",
    "copy-item ",
    "move-item ",
    "get-childitem",
    "get-location",
    "set-location ",
    "new-item ",
    "select-string ",
    "where-object ",
    "foreach-object ",
    "resolve-path ",
    "join-path ",
    "split-path ",
    "python ",
    "py ",
    "pytest ",
    "pip ",
    "git ",
    "cd ",
)


def looks_like_terminal_command(text: str) -> bool:
    """Return True for command-shaped input meant for PowerShell/terminal.

    The interactive Mary prompt never executes these commands.  This helper is
    only a usability guard so command text is not accidentally sent to the LLM
    and described as though Mary had or lacked a capability.
    """

    value = str(text or "").strip()
    if not value:
        return False

    lowered = value.lower()

    # Natural-language questions about commands should still reach Mary.
    if lowered.startswith((
        "what ",
        "why ",
        "how ",
        "explain ",
        "tell me ",
    )):
        return False

    if lowered in {"dir", "ls", "pwd"}:
        return True

    return lowered.startswith(_POWERSHELL_PREFIXES)


def terminal_command_guidance(text: str) -> str:
    """Explain where a terminal-shaped command should be entered."""

    command = str(text or "").strip()
    return (
        "That looks like a PowerShell/terminal command, so I did not execute "
        "or send it through Mary's reasoning pipeline.\n\n"
        f"Run this at the PowerShell prompt instead:\n{command}\n\n"
        "You can use a second VS Code terminal while Mary stays open, or type "
        "`exit` here first and then run the command."
    )


def format_pending_requests(application: "MaryApplication") -> str:
    """Return a compact creator-facing list of pending approvals."""

    pending = application.mary.tools.pending_requests()
    if not pending:
        return "There are no pending tool requests."

    lines = ["Pending tool requests:"]
    for request in pending:
        lines.append(
            f"- {request.request_id}: {request.tool_name}"
        )

    if len(pending) == 1:
        lines.append("Say `approve` to approve it, or `reject` to reject it.")
    else:
        lines.append(
            "More than one request is pending. Use `approve request_...` or "
            "`reject request_...` with the exact id."
        )

    return "\n".join(lines)


def interactive_help(application: "MaryApplication") -> str:
    """Explain the difference between Mary's prompt and PowerShell."""

    workspace = application.mary.tools.workspace_root
    return (
        "MaryV2 terminal help\n\n"
        "At `You:` type requests for Mary, for example:\n"
        "  who are you?\n"
        "  remember that my test animal is a red panda\n"
        "  show me what's in mary/memory\n"
        "  analyze mary/memory/manager.py\n"
        "  create file test.txt with hello\n\n"
        "PowerShell commands do NOT belong at the `You:` prompt, for example:\n"
        "  python -m pytest tests -q\n"
        "  Test-Path test.txt\n"
        "  Get-Content test.txt\n"
        "  Remove-Item test.txt\n\n"
        "Run those in a VS Code PowerShell terminal instead. You can open a "
        "second terminal while Mary stays running.\n\n"
        "Inside Mary, `/pending` shows pending approvals. If exactly one request "
        "is pending, simply type `approve` or `reject`.\n\n"
        f"Mary's bounded workspace is: {workspace}"
    )


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

    # Memory is loaded here, after Mary construction.  Give the relationship
    # system one conservative pass over durable explicit creator statements so
    # older V2 memories can populate the structured creator model without
    # promoting arbitrary conversation or inference.
    sync_relationship = getattr(
        mary,
        "_sync_relationship_from_existing_memories",
        None,
    )
    if callable(sync_relationship):
        sync_relationship()

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
    print("At 'You:' type requests for Mary, not PowerShell commands.")
    print("Type '/help' for examples, '/pending' for approvals, or 'exit' to stop.")
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

            command = user_input.lower()

            if command in {"/help", "/h"}:
                print(f"Mary: {interactive_help(app)}")
                continue

            if command in {"/pending", "pending", "pending requests"}:
                print(f"Mary: {format_pending_requests(app)}")
                continue

            if looks_like_terminal_command(user_input):
                print(f"Mary: {terminal_command_guidance(user_input)}")
                continue

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
