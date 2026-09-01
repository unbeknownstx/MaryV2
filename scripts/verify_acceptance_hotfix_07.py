"""Verify V2 acceptance Hotfix 07 prompt-efficiency guarantees."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application


class CaptureRouter:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content="Yeah. A lazy day with a sketchbook, something good to eat, and nowhere I have to be sounds pretty perfect.",
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True

    def routing_strategy(self):
        return "configured"

    def _provider_order(self, requested=None, route=None):
        return ["test"]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def _mary(router: CaptureRouter, root: Path):
    app = create_application(
        memory_path=root / "data" / "memory" / "memory.json",
        auto_save=False, load_memory=False, load_developed_self=False,
        load_preference_promotion=False, load_knowledge=False,
    )
    mary = app.mary
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return app


def _combined_prompt(router: CaptureRouter) -> str:
    messages, _kwargs = router.calls[0]
    return "\n".join(str(message.content) for message in messages)


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def main() -> None:
    print("=" * 72)
    print("MARY V2 ACCEPTANCE HOTFIX 07 - PROMPT EFFICIENCY")
    print("=" * 72)

    original_cwd = Path.cwd()
    with TemporaryDirectory(prefix="maryv2_hf07_") as temp:
        os.chdir(temp)
        try:
            router = CaptureRouter()
            app = _mary(router, Path(temp))
            mary = app.mary
            _turn(app, "Hey Mary, what would your perfect lazy day look like?")
            combined = _combined_prompt(router)

            check("normal conversation prompt remains below the canonical 14k ceiling", len(combined) < 14_000)
            check("compact TurnMindState remains present", "Compact TurnMindState" in combined)
            check("character-first system policy remains present", "not a generic customer-service assistant" in combined)

            router = CaptureRouter()
            app.close()
            app = _mary(router, Path(temp))
            mary = app.mary
            mary.user_model.facts = {f"fact_{i}": "x" * 220 for i in range(40)}
            mary.user_model.preferences = {f"pref_{i}": "y" * 220 for i in range(40)}
            mary.user_model.interests = [f"interest {i} " + "z" * 220 for i in range(40)]
            mary.user_model.values = [f"value {i} " + "v" * 220 for i in range(40)]
            mary.user_model.goals = [f"goal {i} " + "g" * 220 for i in range(40)]
            mary.user_model.communication_style = {f"style_{i}": "s" * 220 for i in range(40)}
            _turn(app, "Hey Mary, what would your perfect lazy day look like?")
            combined = _combined_prompt(router)

            check("large durable creator profile stays below the canonical 14k ceiling", len(combined) < 14_000)
            check("ordinary generation does not serialize the tail of a huge creator profile", "fact_39" not in combined and "goal 39" not in combined)
        finally:
            app.close()
            os.chdir(original_cwd)

    print("=" * 72)
    print("ACCEPTANCE HOTFIX 07 VERIFIED")


if __name__ == "__main__":
    main()
