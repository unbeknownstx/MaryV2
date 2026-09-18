"""Experience replay and skill-distillation substrate for MaryV2.

This stores structural outcomes of typed work, never hidden chain-of-thought.
Successful verified episodes can form procedural-skill candidates after repeated
evidence. Candidates never self-approve and no replay record grants permission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _tuple(values: Iterable[Any], *, limit: int = 32, item_limit: int = 180) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item
            for raw in list(values)[:limit]
            if (item := _text(raw, item_limit))
        )
    )


def _repeat_key(capability: str, operation: str, tags: Iterable[str]) -> str:
    parts = [
        _text(capability, 120).casefold(),
        _text(operation, 80).casefold(),
        *sorted(_text(tag, 80).casefold() for tag in list(tags)[:8] if _text(tag, 80)),
    ]
    return "|".join(part for part in parts if part)[:600]


@dataclass(frozen=True)
class ReplayEpisode:
    id: str
    source_task_id: str
    root_task_id: str
    capability: str
    operation: str
    objective: str
    node_id: str
    status: str
    success: bool
    verified: bool
    public_steps: tuple[str, ...]
    verification: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    tags: tuple[str, ...]
    repeat_key: str
    outcome_summary: str
    occurred_at: str
    attempt: int = 1


@dataclass(frozen=True)
class ReplayLesson:
    id: str
    lesson_type: str
    repeat_key: str
    summary: str
    source_episode_ids: tuple[str, ...]
    success_rate: float
    confidence: float
    status: str
    created_at: str


class ExperienceReplayStore:
    """Durable structural replay below canonical Mary state."""

    VERSION = 1

    def __init__(self, path: Path, *, episode_capacity: int = 4000, lesson_capacity: int = 1200) -> None:
        self.episode_capacity = max(128, int(episode_capacity))
        self.lesson_capacity = max(64, int(lesson_capacity))
        self._store = AtomicJsonStore(
            path,
            default={
                "version": self.VERSION,
                "episodes": [],
                "lessons": [],
                "distilled_keys": [],
            },
        )

    def record_episode(
        self,
        *,
        source_task_id: str,
        capability: str,
        objective: str,
        node_id: str,
        status: str,
        success: bool,
        verified: bool = False,
        operation: str = "general",
        root_task_id: str = "",
        public_steps: Iterable[str] = (),
        verification: Iterable[str] = (),
        evidence_ids: Iterable[str] = (),
        tags: Iterable[str] = (),
        outcome_summary: str = "",
        attempt: int = 1,
        occurred_at: str | None = None,
    ) -> ReplayEpisode:
        """Record one idempotent structural outcome keyed by source_task_id."""

        task_id = _text(source_task_id, 180)
        if not task_id:
            raise ValueError("replay episode requires source_task_id")
        clean_capability = _text(capability, 160).casefold()
        clean_operation = _text(operation, 80).casefold() or "general"
        clean_tags = _tuple(tags, limit=24, item_limit=80)
        key = _repeat_key(clean_capability, clean_operation, clean_tags)
        existing = self.by_task(task_id)
        if existing is not None:
            return existing

        episode = ReplayEpisode(
            id=f"replay_{uuid4().hex}",
            source_task_id=task_id,
            root_task_id=_text(root_task_id, 180),
            capability=clean_capability,
            operation=clean_operation,
            objective=_text(objective, 1200),
            node_id=_text(node_id, 180),
            status=_text(status, 80).casefold(),
            success=bool(success),
            verified=bool(verified),
            public_steps=_tuple(public_steps, limit=24, item_limit=400),
            verification=_tuple(verification, limit=24, item_limit=300),
            evidence_ids=_tuple(evidence_ids, limit=48, item_limit=180),
            tags=clean_tags,
            repeat_key=key,
            outcome_summary=_text(outcome_summary, 1200),
            occurred_at=occurred_at or _now(),
            attempt=max(1, min(20, int(attempt or 1))),
        )

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("episodes") or [])
            if any(str(row.get("source_task_id") or "") == task_id for row in rows):
                return
            payload = asdict(episode)
            for name in ("public_steps", "verification", "evidence_ids", "tags"):
                payload[name] = list(payload[name])
            rows.append(payload)
            data["episodes"] = rows[-self.episode_capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return self.by_task(task_id) or episode

    def by_task(self, source_task_id: str) -> ReplayEpisode | None:
        key = str(source_task_id or "").strip()
        for row in reversed(list(self._store.snapshot().get("episodes") or [])):
            if str(row.get("source_task_id") or "") == key:
                return self._decode_episode(row)
        return None

    def recent(self, *, limit: int = 50) -> list[ReplayEpisode]:
        rows = list(self._store.snapshot().get("episodes") or [])
        return [
            self._decode_episode(row)
            for row in rows[-max(1, min(500, int(limit))) :]
        ][::-1]

    def similar(self, query: str, *, limit: int = 12) -> list[ReplayEpisode]:
        terms = {
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9_.-]{3,}", str(query or ""))
        }
        if not terms:
            return self.recent(limit=limit)
        scored: list[tuple[float, ReplayEpisode]] = []
        for episode in self.recent(limit=500):
            haystack = " ".join([
                episode.capability,
                episode.operation,
                episode.objective,
                episode.outcome_summary,
                " ".join(episode.public_steps),
                " ".join(episode.tags),
            ]).casefold()
            lexical = sum(1.0 for term in terms if term in haystack)
            if lexical <= 0:
                continue
            score = lexical + (0.35 if episode.verified else 0.0) + (0.2 if episode.success else 0.0)
            scored.append((score, episode))
        scored.sort(key=lambda item: (item[0], item[1].occurred_at), reverse=True)
        return [item[1] for item in scored[: max(1, min(50, int(limit)))]]

    def consolidate(
        self,
        skill_library: Any,
        *,
        minimum_attempts: int = 3,
        minimum_success_rate: float = 0.8,
    ) -> dict[str, Any]:
        """Create lesson/skill candidates from repeated verified outcomes only."""

        snapshot = self._store.snapshot()
        episodes = [self._decode_episode(row) for row in list(snapshot.get("episodes") or [])]
        groups: dict[str, list[ReplayEpisode]] = {}
        for episode in episodes:
            if episode.repeat_key:
                groups.setdefault(episode.repeat_key, []).append(episode)

        distilled = set(str(item) for item in list(snapshot.get("distilled_keys") or []))
        lessons_created: list[ReplayLesson] = []
        skills_created: list[str] = []
        newly_distilled: list[str] = []

        for key, group in sorted(groups.items()):
            if key in distilled or len(group) < max(2, int(minimum_attempts)):
                continue
            successes = [item for item in group if item.success and item.verified]
            failures = [item for item in group if not item.success]
            rate = len(successes) / max(1, len(group))
            source_ids = tuple(item.id for item in group[-16:])

            if len(successes) >= minimum_attempts and rate >= minimum_success_rate:
                exemplar = successes[-1]
                common_steps = self._common_steps(successes)
                lesson = ReplayLesson(
                    id=f"lesson_{uuid4().hex}",
                    lesson_type="repeatable_success",
                    repeat_key=key,
                    summary=(
                        f"Repeated verified success for {exemplar.capability} "
                        f"({len(successes)}/{len(group)} successful verified episodes)."
                    ),
                    source_episode_ids=source_ids,
                    success_rate=round(rate, 4),
                    confidence=round(min(0.98, 0.55 + 0.08 * len(successes)), 4),
                    status="candidate",
                    created_at=_now(),
                )
                lessons_created.append(lesson)
                skill = skill_library.register_candidate(
                    name=self._skill_name(exemplar),
                    description=(
                        f"Replay-distilled procedural candidate for {exemplar.capability}. "
                        "Creator approval is required before retrieval/execution eligibility."
                    ),
                    source="experience_replay",
                    required_capabilities=(exemplar.capability,),
                    required_permissions=(exemplar.capability,),
                    steps=common_steps or exemplar.public_steps or (f"Use {exemplar.capability}",),
                    verification=exemplar.verification or ("verify typed task outcome",),
                    failure_recovery=(
                        "stop and preserve failure evidence",
                        "do not repeat consequential action automatically",
                    ),
                    preconditions=(
                        "matching capability is connected",
                        "required local permission remains granted",
                    ),
                    tags=(*exemplar.tags, "replay_distilled"),
                    origin_experience_ids=source_ids,
                    confidence=lesson.confidence,
                )
                skills_created.append(skill.id)
                newly_distilled.append(key)
                continue

            if len(failures) >= minimum_attempts:
                lesson = ReplayLesson(
                    id=f"lesson_{uuid4().hex}",
                    lesson_type="failure_pattern",
                    repeat_key=key,
                    summary=(
                        f"Repeated failure pattern for {failures[-1].capability}: "
                        f"{len(failures)}/{len(group)} unsuccessful episode(s)."
                    ),
                    source_episode_ids=source_ids,
                    success_rate=round(rate, 4),
                    confidence=round(min(0.95, 0.5 + 0.07 * len(failures)), 4),
                    status="candidate",
                    created_at=_now(),
                )
                lessons_created.append(lesson)
                newly_distilled.append(key)

        if lessons_created or newly_distilled:
            def mutate(data: dict[str, Any]) -> None:
                rows = list(data.get("lessons") or [])
                for lesson in lessons_created:
                    payload = asdict(lesson)
                    payload["source_episode_ids"] = list(lesson.source_episode_ids)
                    rows.append(payload)
                data["lessons"] = rows[-self.lesson_capacity :]
                keys = list(data.get("distilled_keys") or [])
                keys.extend(newly_distilled)
                data["distilled_keys"] = list(dict.fromkeys(keys))[-self.episode_capacity :]

            self._store.mutate(mutate)

        return {
            "episodes_considered": len(episodes),
            "lessons_created": len(lessons_created),
            "skill_candidates_created": len(skills_created),
            "skill_candidate_ids": skills_created,
            "promotion_performed": False,
        }

    def lessons(self, *, status: str = "candidate", limit: int = 100) -> list[ReplayLesson]:
        output: list[ReplayLesson] = []
        for row in reversed(list(self._store.snapshot().get("lessons") or [])):
            if str(row.get("status") or "") != status:
                continue
            output.append(self._decode_lesson(row))
            if len(output) >= max(1, min(500, int(limit))):
                break
        return output

    def set_lesson_status(self, lesson_id: str, status: str) -> ReplayLesson:
        allowed = {"candidate", "approved", "rejected", "archived"}
        if status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        found = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("lessons") or []):
                if str(row.get("id") or "") == lesson_id:
                    row["status"] = status
                    found = True
                    break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(lesson_id)
        for item in self.lessons(status=status, limit=500):
            if item.id == lesson_id:
                return item
        raise KeyError(lesson_id)

    def status(self) -> dict[str, Any]:
        data = self._store.snapshot()
        episodes = list(data.get("episodes") or [])
        lessons = list(data.get("lessons") or [])
        return {
            "version": self.VERSION,
            "episodes": len(episodes),
            "successful": sum(1 for row in episodes if bool(row.get("success"))),
            "verified": sum(1 for row in episodes if bool(row.get("verified"))),
            "lessons": len(lessons),
            "pending_lessons": sum(
                1 for row in lessons if str(row.get("status") or "") == "candidate"
            ),
            "distilled_patterns": len(data.get("distilled_keys") or []),
            "authority": (
                "structural learning evidence only; no identity/memory truth, "
                "permission or automatic skill approval"
            ),
        }

    @staticmethod
    def _skill_name(exemplar: ReplayEpisode) -> str:
        label = exemplar.capability.replace(".", " ").replace("_", " ").strip()
        return f"learned: {label}"[:160]

    @staticmethod
    def _common_steps(episodes: list[ReplayEpisode]) -> tuple[str, ...]:
        if not episodes:
            return ()
        common = list(episodes[-1].public_steps)
        for episode in episodes[:-1]:
            available = set(episode.public_steps)
            common = [step for step in common if step in available]
        return tuple(common[:24])

    @staticmethod
    def _decode_episode(row: dict[str, Any]) -> ReplayEpisode:
        values = dict(row)
        for name in ("public_steps", "verification", "evidence_ids", "tags"):
            values[name] = tuple(values.get(name) or [])
        values.setdefault("root_task_id", "")
        values.setdefault("operation", "general")
        values.setdefault("attempt", 1)
        return ReplayEpisode(**values)

    @staticmethod
    def _decode_lesson(row: dict[str, Any]) -> ReplayLesson:
        values = dict(row)
        values["source_episode_ids"] = tuple(values.get("source_episode_ids") or [])
        return ReplayLesson(**values)
