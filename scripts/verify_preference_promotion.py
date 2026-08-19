from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from mary.core.mary import Mary
from mary.runtime.application import create_application


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS {message}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 PREFERENCE PROMOTION")
    print("=" * 72)

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        memory_path = root / "memory" / "memory.json"
        developed_path = root / "personality" / "developed_self.json"
        promotion_path = root / "personality" / "preference_promotion.json"

        plain = Mary()
        _check(
            plain.preference_promotion.configured is False,
            "plain Mary keeps tentative preference evidence nonpersistent",
        )

        blocked = False
        try:
            plain.observe_preference_experience(
                "invented favorite",
                source="model_dialogue",
                confidence=1.0,
            )
        except ValueError:
            blocked = True

        _check(
            blocked and plain.preferences.get_preference("invented favorite") is None,
            "model dialogue cannot become preference-development evidence",
        )

        app = create_application(
            memory_path=memory_path,
            developed_self_path=developed_path,
            preference_promotion_path=promotion_path,
            auto_save=True,
        )

        for index in range(1, 4):
            evaluation = app.mary.observe_preference_experience(
                "late-night jazz",
                category="music",
                strength=0.8,
                polarity=1.0,
                confidence=0.9,
                source="experience",
                evidence_id=f"experience-{index}",
            )

            if index < 3:
                _check(
                    evaluation["eligible"] is False,
                    f"observation {index} remains tentative",
                )

        _check(
            evaluation["eligible"] is True,
            "three consistent high-confidence observations become eligible",
        )
        _check(
            app.mary.preferences.get_preference("late-night jazz") is None,
            "eligibility alone does not mutate Mary's represented preferences",
        )

        promoted = app.mary.promote_preference_candidate("late-night jazz")
        _check(
            promoted["promoted"] is True,
            "explicit promotion creates developed preference",
        )
        app.close()

        second = create_application(
            memory_path=memory_path,
            developed_self_path=developed_path,
            preference_promotion_path=promotion_path,
            auto_save=True,
        )
        restored = second.mary.preferences.get_preference("late-night jazz")
        _check(
            restored is not None
            and restored.get("source") == "experience_promotion",
            "promoted preference survives restart through developed self-state",
        )
        _check(
            second.mary.preference_promotion.get_candidate("late-night jazz") is None,
            "promoted candidate is no longer tentative after restart",
        )
        second.close()

    print("-" * 72)
    print("RESULT: PASS")
    print(
        "Preference development now requires repeated grounded evidence plus "
        "an explicit durable promotion step."
    )


if __name__ == "__main__":
    main()
