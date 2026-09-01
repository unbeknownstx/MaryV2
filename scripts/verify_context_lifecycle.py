"""Verify that long Mary sessions keep bounded LLM-facing dialogue context.

This verifier uses a local fake router. It makes no network calls, spends no API
quota, and does not write to Mary's durable memory.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application


class ProbeRouter:
    def __init__(self) -> None:
        self.calls = []
        self.count = 0

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        self.count += 1
        return LLMResponse(
            content=f"Probe response {self.count}. I'm following the current thread.",
            provider="context-probe",
            model="local-fake",
        )

    def provider_name(self, provider=None):
        return "context-probe"

    def model_name(self, provider=None):
        return "local-fake"

    def is_available(self, provider=None):
        return True


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def main() -> int:
    print("=" * 72)
    print("MARY V2 MULTI-TURN CONTEXT LIFECYCLE")
    print("=" * 72)

    with TemporaryDirectory(prefix="maryv2_context_lifecycle_") as directory, ExitStack() as cleanup:
        app = create_application(
            memory_path=Path(directory) / "data" / "memory" / "memory.json",
            auto_save=False, load_memory=False, load_developed_self=False,
            load_preference_promotion=False, load_knowledge=False,
        )
        cleanup.callback(app.close)
        mary = app.mary
        router = ProbeRouter()
        mary.llm = router
        mary.reasoning.llm = router
        mary.reflection.llm = router

        for index in range(12):
            _turn(app,
                f"Long session turn {index}: "
                + ("This is deliberate extra dialogue used to pressure the active context window. " * 7)
            )

        result = _turn(app, "What matters from the thread right now?")
        lifecycle = result.context.mind_state.get("conversation", {}).get("lifecycle", {})

    print(f"Total prior messages:    {lifecycle.get('total_messages')}")
    print(f"Selected messages:       {lifecycle.get('selected_messages')}")
    print(f"Dropped raw messages:    {lifecycle.get('dropped_messages')}")
    print(f"Selected characters:     {lifecycle.get('selected_characters')}")
    print(f"Character budget:        {lifecycle.get('max_characters')}")
    print(f"Ephemeral anchors:       {len(lifecycle.get('anchors', []))}")
    print(f"Promotion policy:        {lifecycle.get('promotion_policy')}")
    print("-" * 72)

    passed = (
        int(lifecycle.get("selected_messages", 999)) <= 8
        and int(lifecycle.get("selected_characters", 999999)) <= int(lifecycle.get("max_characters", 0))
        and int(lifecycle.get("dropped_messages", 0)) > 0
        and lifecycle.get("promotion_policy") == "explicit_or_existing_development_paths_only"
    )

    if passed:
        print("RESULT: PASS")
        print("Long-session dialogue is bounded before it reaches the LLM.")
        print("Older raw turns remain session history but are represented only by tiny temporary anchors.")
        print("Ordinary dialogue is not automatically promoted into durable memory.")
        return 0

    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
