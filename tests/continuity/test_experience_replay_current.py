from __future__ import annotations

from pathlib import Path

from mary.continuity import ExperienceReplayStore, SkillLibrary


def test_replay_is_idempotent_and_never_auto_approves_skill(tmp_path: Path) -> None:
    replay = ExperienceReplayStore(tmp_path / "replay.json")
    skills = SkillLibrary(tmp_path / "skills.json")

    for index in range(3):
        episode = replay.record_episode(
            source_task_id=f"task-{index}",
            root_task_id=f"task-{index}",
            capability="engineering.structure.verify",
            operation="test",
            objective="Verify repository structure",
            node_id="windows-pc",
            status="completed",
            success=True,
            verified=True,
            public_steps=(
                "dispatch typed capability engineering.structure.verify",
                "receive terminal node status completed",
            ),
            verification=("typed repository validation result",),
            evidence_ids=(f"task-{index}",),
            tags=("engineering", "test"),
            outcome_summary="Repository structure verified.",
        )
        assert episode.success is True

    duplicate = replay.record_episode(
        source_task_id="task-0",
        capability="engineering.structure.verify",
        operation="test",
        objective="duplicate",
        node_id="windows-pc",
        status="failed",
        success=False,
    )
    assert duplicate.success is True
    assert replay.status()["episodes"] == 3

    result = replay.consolidate(skills)
    assert result["skill_candidates_created"] == 1
    assert result["promotion_performed"] is False

    candidates = skills.candidates()
    assert len(candidates) == 1
    assert candidates[0].status == "candidate"
    assert candidates[0].source == "experience_replay"
    assert "engineering.structure.verify" in candidates[0].required_capabilities

    # Maintenance/replay cannot silently make the skill executable.
    assert skills.eligible(
        capabilities={"engineering.structure.verify"},
        permissions={"engineering.structure.verify"},
    ) == []


def test_repeated_failures_create_lesson_not_skill(tmp_path: Path) -> None:
    replay = ExperienceReplayStore(tmp_path / "replay.json")
    skills = SkillLibrary(tmp_path / "skills.json")

    for index in range(3):
        replay.record_episode(
            source_task_id=f"failed-{index}",
            capability="vision.gui.ground",
            operation="perception",
            objective="Ground a requested UI target",
            node_id="vision-node",
            status="failed",
            success=False,
            verified=False,
            tags=("vision", "gui"),
            outcome_summary="Grounding failed.",
        )

    result = replay.consolidate(skills)

    assert result["skill_candidates_created"] == 0
    assert result["lessons_created"] == 1
    lesson = replay.lessons()[0]
    assert lesson.lesson_type == "failure_pattern"
    assert lesson.success_rate == 0.0
    assert skills.status()["skills"] == 0


def test_replay_similarity_returns_structural_evidence_only(tmp_path: Path) -> None:
    replay = ExperienceReplayStore(tmp_path / "replay.json")
    replay.record_episode(
        source_task_id="task-vision",
        capability="vision.gui.ground",
        operation="perception",
        objective="Typed capability task: vision.gui.ground",
        node_id="mac",
        status="completed",
        success=True,
        verified=True,
        public_steps=("dispatch typed capability vision.gui.ground",),
        verification=("node completion",),
        tags=("vision", "gui"),
        outcome_summary="GUI target grounded.",
    )
    replay.record_episode(
        source_task_id="task-code",
        capability="engineering.repo.inspect",
        operation="engineering",
        objective="Typed capability task: engineering.repo.inspect",
        node_id="windows",
        status="completed",
        success=True,
        verified=True,
        tags=("engineering",),
        outcome_summary="Repository evidence inspected.",
    )

    hits = replay.similar("vision gui")
    assert hits
    assert hits[0].source_task_id == "task-vision"
    assert not hasattr(hits[0], "chain_of_thought")
    assert not hasattr(hits[0], "raw_provider_payload")
