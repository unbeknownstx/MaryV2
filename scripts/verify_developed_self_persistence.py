"""Verify MaryV2 developed-self wiring and persistence without external services."""

from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.runtime.application import create_application


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 DEVELOPED-SELF PERSISTENCE")
    print("=" * 72)

    direct_app = create_application(
        auto_save=False, load_memory=False, load_developed_self=False,
        load_preference_promotion=False, load_knowledge=False,
    )
    direct = direct_app.mary
    check(
        "canonical application keeps developed-self persistence isolated when loading is disabled",
        direct.developed_self_state.configured,
    )
    check(
        "PersonalityDevelopment is wired to Mary's live Values and Preferences",
        direct.personality_development.personality is direct.personality
        and direct.personality_development.values is direct.values
        and direct.personality_development.preferences is direct.preferences,
    )
    check(
        "authored character preferences stay canonical instead of being serialized as development",
        direct.developed_self_state.to_dict()["preference_overrides"] == {},
    )
    direct_app.close()

    with TemporaryDirectory() as directory, ExitStack() as cleanup:
        root = Path(directory)
        memory_path = root / "memory" / "memory.json"
        developed_path = root / "personality" / "developed_self.json"

        first = create_application(
            memory_path=memory_path,
            developed_self_path=developed_path,
            auto_save=True,
        )
        cleanup.callback(first.close)
        first.mary.set_developed_preference(
            "quiet bookstores",
            category="places",
            strength=0.77,
            confidence=0.9,
            source="experience",
        )
        first.close()

        check(
            "explicit experience preference writes developed_self.json",
            developed_path.exists(),
        )

        payload = json.loads(developed_path.read_text(encoding="utf-8"))
        check(
            "developed_self.json excludes character_core preference copies",
            all(
                item.get("source") != "character_core"
                for item in payload.get("preference_overrides", {}).values()
            ),
        )

        second = create_application(
            memory_path=memory_path,
            developed_self_path=developed_path,
            auto_save=True,
        )
        cleanup.callback(second.close)
        restored = second.mary.preferences.get_preference("quiet bookstores")
        check(
            "developed preference survives a fresh persistent Mary runtime",
            restored is not None
            and restored.get("source") == "experience"
            and abs(float(restored.get("strength", 0.0)) - 0.77) < 1e-9,
        )
        second.close()

        personality_path = root / "personality" / "personality_restart.json"
        third = create_application(
            memory_path=memory_path,
            developed_self_path=personality_path,
            auto_save=True,
        )
        cleanup.callback(third.close)
        target_warmth = 0.61
        third.mary.personality.set_trait("warmth", target_warmth)
        third.mary.developed_self_state.record_approved_personality_change(
            {"trait": "warmth", "source": "approved_verifier"}
        )
        third.close()

        fourth = create_application(
            memory_path=memory_path,
            developed_self_path=personality_path,
            auto_save=True,
        )
        cleanup.callback(fourth.close)
        check(
            "approved personality end-state restores as an exact value",
            abs(fourth.mary.personality.get_trait("warmth") - target_warmth) < 1e-9,
        )
        fourth.close()

    blocked = False
    try:
        direct.set_developed_preference(
            "model-invented favorite",
            source="model_dialogue",
        )
    except ValueError:
        blocked = True

    check(
        "model dialogue is rejected as a durable preference source",
        blocked,
    )

    print("-" * 72)
    print("RESULT: PASS")
    print("Mary's developed self now has an explicit durable persistence boundary.")


if __name__ == "__main__":
    main()
