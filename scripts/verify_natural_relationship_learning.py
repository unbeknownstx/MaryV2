from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path
import os

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application


class FakeRouter:
    def generate(self, messages, **kwargs):
        return LLMResponse(
            content="Got it.",
            provider="test",
            model="natural-learning-fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "natural-learning-fake"

    def is_available(self, provider=None):
        return True


def wire(mary: Mary) -> None:
    router = FakeRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.conversation.router = router


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS {message}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 NATURAL RELATIONSHIP LEARNING")
    print("=" * 72)

    original = Path.cwd()
    with TemporaryDirectory() as temp:
        os.chdir(temp)
        try:
            mary = Mary()
            wire(mary)

            result = mary.process(
                "I prefer you to give me quick updates while you work."
            )
            meta = result.metadata.get("natural_relationship_learning", {})
            check(meta.get("learned") is True, "clear creator statement learns without magic prefix")
            check(
                "quick updates" in mary.relationship.answer_query("preferences").lower(),
                "natural share enters the existing structured creator model",
            )
            check(
                mary.preferences.get_preference("quick updates") is None,
                "creator preference remains separate from Mary's preferences",
            )

            before = mary.memory.episodic.count()
            duplicate = mary.process(
                "I prefer you to give me quick updates while you work."
            )
            after = mary.memory.episodic.count()
            check(
                duplicate.metadata["natural_relationship_learning"].get("already_known") is True
                and before == after,
                "duplicate natural share does not duplicate durable memory",
            )

            uncertain = mary.process("I might prefer long detailed updates.")
            check(
                "natural_relationship_learning" not in uncertain.metadata,
                "uncertain statement stays ordinary conversation",
            )

            memory_path = Path(temp) / "persistent" / "memory.json"
            developed_path = Path(temp) / "persistent" / "developed_self.json"
            promotion_path = Path(temp) / "persistent" / "preference_promotion.json"

            first = create_application(
                memory_path=memory_path,
                developed_self_path=developed_path,
                preference_promotion_path=promotion_path,
                auto_save=True,
            )
            wire(first.mary)
            first.mary.process("I'm interested in animation.")
            first.close()

            second = create_application(
                memory_path=memory_path,
                developed_self_path=developed_path,
                preference_promotion_path=promotion_path,
                auto_save=True,
            )
            check(
                "animation" in second.mary.relationship.answer_query("interests").lower(),
                "natural relationship knowledge survives restart",
            )
            second.close()
        finally:
            os.chdir(original)

    print("-" * 72)
    print("RESULT: PASS")
    print("Ordinary clear creator shares now feed Mary's existing relationship model conservatively.")


if __name__ == "__main__":
    main()
