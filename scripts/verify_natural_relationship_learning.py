from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path
import os

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


def wire(mary) -> None:
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
        app = None
        first = None
        second = None
        os.chdir(temp)
        try:
            app = create_application()
            mary = app.mary
            wire(mary)

            result = app.run(
                "I prefer you to give me quick updates while you work."
            ).metadata["pipeline_values"]["cognitive_cycle"]
            meta = result.metadata.get("natural_relationship_learning", {})
            check(meta.get("learned") is True, "clear creator statement learns without magic prefix")
            profile = mary.relationship.profile()
            check(
                "quick updates" in str(profile.get("communication_style", {})).lower()
                and "quick updates" in mary.relationship.answer_query("overview").lower(),
                "natural share enters the existing structured creator model",
            )
            check(
                mary.preferences.get_preference("quick updates") is None,
                "creator preference remains separate from Mary's preferences",
            )

            preview_before = len(mary.user_model.get_profile_records(current_only=False))
            preview = mary.relationship.preview_explicit("I value patience.")
            preview_after = len(mary.user_model.get_profile_records(current_only=False))
            check(
                preview is not None
                and preview.get("already_known") is False
                and preview_before == preview_after,
                "relationship preview is pure and non-mutating",
            )

            liked = app.run("I like synthwave music.").metadata["pipeline_values"]["cognitive_cycle"]
            check(
                liked.metadata.get("natural_relationship_learning", {}).get("learned") is True
                and "synthwave" in mary.relationship.answer_query("interests").lower(),
                "direct I-like statement becomes creator-owned interest",
            )

            before = mary.memory.episodic.count()
            duplicate = app.run(
                "I prefer you to give me quick updates while you work."
            ).metadata["pipeline_values"]["cognitive_cycle"]
            after = mary.memory.episodic.count()
            check(
                duplicate.metadata["natural_relationship_learning"].get("already_known") is True
                and before == after,
                "duplicate natural share does not duplicate durable memory",
            )

            uncertain = app.run("I might prefer long detailed updates.").metadata["pipeline_values"]["cognitive_cycle"]
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
            first.run("I'm interested in animation.")
            first.close()
            first = None

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
            second = None
        finally:
            if second is not None:
                second.close()
            if first is not None:
                first.close()
            if app is not None:
                app.close()
            os.chdir(original)

    print("-" * 72)
    print("RESULT: PASS")
    print("Ordinary clear creator shares now feed Mary's existing relationship model conservatively.")


if __name__ == "__main__":
    main()
