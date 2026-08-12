"""
MaryV2 - Learning Experiments

Provides a controlled framework for experimentation.

Mary can use experiments to:

    1. Form a hypothesis.
    2. Define an expected outcome.
    3. Execute an experiment through a supplied action.
    4. Record the actual outcome.
    5. Compare expected vs actual results.
    6. Determine whether the hypothesis was supported.
    7. Preserve the result for future learning.

This module does NOT directly modify Mary's architecture, source
code, personality, memory, or knowledge.

It provides the experiment record and execution infrastructure.

Future architecture:

    Curiosity
        ↓
    Hypothesis
        ↓
    Experiment
        ↓
    Action / Tool
        ↓
    Observation
        ↓
    Evaluation
        ↓
    Learning
        ↓
    Knowledge / Behavior
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


# ================================================================
# EXPERIMENT
# ================================================================


@dataclass
class Experiment:
    """
    Represents one learning experiment.
    """

    id: str

    title: str

    hypothesis: str

    expected_outcome: str

    status: str = "planned"

    actual_outcome: str | None = None

    result: str | None = None

    confidence: float = 0.5

    created_at: str = ""

    started_at: str | None = None

    completed_at: str | None = None

    observations: list[str] = field(
        default_factory=list
    )

    lessons: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()

        self.confidence = _clamp(
            self.confidence
        )


# ================================================================
# EXPERIMENT MANAGER
# ================================================================


class ExperimentManager:
    """
    Creates and manages controlled learning experiments.

    The manager itself does not decide what Mary should experiment
    with. That decision belongs to higher-level systems such as
    curiosity, agency, or the learner.
    """

    VALID_STATUSES = {
        "planned",
        "running",
        "completed",
        "failed",
        "cancelled",
    }

    VALID_RESULTS = {
        "supported",
        "partially_supported",
        "unsupported",
        "inconclusive",
    }

    def __init__(self) -> None:
        self.experiments: list[
            Experiment
        ] = []

    # ============================================================
    # CREATE
    # ============================================================

    def create(
        self,
        title: str,
        hypothesis: str,
        expected_outcome: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Experiment:
        """
        Create a new planned experiment.
        """

        experiment = Experiment(
            id=self._next_id(),
            title=str(
                title
            ).strip(),
            hypothesis=str(
                hypothesis
            ).strip(),
            expected_outcome=str(
                expected_outcome
            ).strip(),
            metadata=metadata or {},
        )

        self.experiments.append(
            experiment
        )

        return experiment

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        experiment_id: str,
    ) -> Experiment | None:
        """
        Retrieve an experiment by ID.
        """

        for experiment in self.experiments:
            if experiment.id == experiment_id:
                return experiment

        return None

    def get_all(
        self,
    ) -> list[Experiment]:
        """
        Return all experiments.
        """

        return list(
            self.experiments
        )

    def get_planned(
        self,
    ) -> list[Experiment]:
        """
        Return experiments waiting to run.
        """

        return [
            experiment
            for experiment in self.experiments
            if experiment.status == "planned"
        ]

    def get_completed(
        self,
    ) -> list[Experiment]:
        """
        Return completed experiments.
        """

        return [
            experiment
            for experiment in self.experiments
            if experiment.status
            == "completed"
        ]

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        experiment_id: str,
    ) -> Experiment | None:
        """
        Start a planned experiment.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        if experiment.status != "planned":
            return experiment

        experiment.status = "running"

        experiment.started_at = (
            _timestamp()
        )

        return experiment

    # ============================================================
    # OBSERVATIONS
    # ============================================================

    def add_observation(
        self,
        experiment_id: str,
        observation: str,
    ) -> bool:
        """
        Record an observation during an experiment.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return False

        experiment.observations.append(
            str(
                observation
            ).strip()
        )

        return True

    # ============================================================
    # COMPLETE
    # ============================================================

    def complete(
        self,
        experiment_id: str,
        actual_outcome: str,
        *,
        result: str = "inconclusive",
        confidence: float = 0.5,
        lesson: str | None = None,
    ) -> Experiment | None:
        """
        Complete an experiment and record its result.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        if result not in self.VALID_RESULTS:
            raise ValueError(
                "Invalid experiment result: "
                f"{result}"
            )

        experiment.status = (
            "completed"
        )

        experiment.actual_outcome = (
            str(
                actual_outcome
            ).strip()
        )

        experiment.result = result

        experiment.confidence = _clamp(
            confidence
        )

        experiment.completed_at = (
            _timestamp()
        )

        if lesson:
            experiment.lessons.append(
                str(
                    lesson
                ).strip()
            )

        return experiment

    # ============================================================
    # FAIL
    # ============================================================

    def fail(
        self,
        experiment_id: str,
        reason: str,
    ) -> Experiment | None:
        """
        Mark an experiment as failed.

        A failed experiment is still useful because failure itself
        can produce information.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        experiment.status = "failed"

        experiment.actual_outcome = (
            str(
                reason
            ).strip()
        )

        experiment.completed_at = (
            _timestamp()
        )

        experiment.lessons.append(
            "Experiment failed: "
            + str(
                reason
            ).strip()
        )

        return experiment

    # ============================================================
    # CANCEL
    # ============================================================

    def cancel(
        self,
        experiment_id: str,
        reason: str = "",
    ) -> Experiment | None:
        """
        Cancel an experiment.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        experiment.status = (
            "cancelled"
        )

        experiment.completed_at = (
            _timestamp()
        )

        if reason:
            experiment.lessons.append(
                "Experiment cancelled: "
                + str(
                    reason
                ).strip()
            )

        return experiment

    # ============================================================
    # EXECUTION
    # ============================================================

    def run(
        self,
        experiment_id: str,
        action: Callable[[], Any],
    ) -> Experiment | None:
        """
        Execute an experiment using a supplied callable.

        The callable is intentionally injected.

        This keeps ExperimentManager independent from:

            - shell commands
            - filesystem access
            - web access
            - code execution
            - external APIs

        Those capabilities belong to the tools layer.
        """

        experiment = self.start(
            experiment_id
        )

        if experiment is None:
            return None

        try:
            outcome = action()

            actual_outcome = _format_outcome(
                outcome
            )

            experiment.actual_outcome = (
                actual_outcome
            )

            experiment.status = (
                "completed"
            )

            experiment.completed_at = (
                _timestamp()
            )

            return experiment

        except Exception as exc:
            self.fail(
                experiment.id,
                str(
                    exc
                ),
            )

            return experiment

    # ============================================================
    # COMPARE
    # ============================================================

    def compare_outcome(
        self,
        experiment_id: str,
    ) -> str | None:
        """
        Perform a basic comparison between the expected and actual
        outcomes.

        This is intentionally conservative.

        Semantic comparison can later be delegated to the LLM.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        if experiment.actual_outcome is None:
            return None

        expected = _normalize(
            experiment.expected_outcome
        )

        actual = _normalize(
            experiment.actual_outcome
        )

        if expected == actual:
            return "supported"

        expected_words = set(
            expected.split()
        )

        actual_words = set(
            actual.split()
        )

        if not expected_words:
            return "inconclusive"

        overlap = (
            len(
                expected_words
                & actual_words
            )
            / len(
                expected_words
            )
        )

        if overlap >= 0.75:
            return "supported"

        if overlap >= 0.35:
            return "partially_supported"

        return "unsupported"

    # ============================================================
    # RECORD RESULT
    # ============================================================

    def record_comparison(
        self,
        experiment_id: str,
        *,
        confidence: float = 0.5,
    ) -> Experiment | None:
        """
        Compare the expected and actual outcome and store the
        resulting classification.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        result = self.compare_outcome(
            experiment_id
        )

        if result is None:
            return experiment

        experiment.result = result

        experiment.confidence = _clamp(
            confidence
        )

        return experiment

    # ============================================================
    # LESSONS
    # ============================================================

    def add_lesson(
        self,
        experiment_id: str,
        lesson: str,
    ) -> bool:
        """
        Record something learned from an experiment.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return False

        lesson = str(
            lesson
        ).strip()

        if not lesson:
            return False

        experiment.lessons.append(
            lesson
        )

        return True

    def get_lessons(
        self,
        experiment_id: str,
    ) -> list[str]:
        """
        Return lessons produced by an experiment.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return []

        return list(
            experiment.lessons
        )

    # ============================================================
    # LEARNING SUMMARY
    # ============================================================

    def summarize(
        self,
        experiment_id: str,
    ) -> dict[str, Any] | None:
        """
        Produce a structured summary that can be passed to the
        learner or knowledge system.
        """

        experiment = self.get(
            experiment_id
        )

        if experiment is None:
            return None

        return {
            "id": experiment.id,
            "title": experiment.title,
            "hypothesis": experiment.hypothesis,
            "expected_outcome": (
                experiment.expected_outcome
            ),
            "actual_outcome": (
                experiment.actual_outcome
            ),
            "result": experiment.result,
            "confidence": (
                experiment.confidence
            ),
            "observations": list(
                experiment.observations
            ),
            "lessons": list(
                experiment.lessons
            ),
            "status": experiment.status,
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> list[dict[str, Any]]:
        """
        Serialize experiment state.
        """

        return [
            asdict(experiment)
            for experiment in self.experiments
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore experiment state.
        """

        self.experiments.clear()

        if not isinstance(
            data,
            list,
        ):
            return

        for entry in data:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            experiment = Experiment(
                id=str(
                    entry.get(
                        "id",
                        "",
                    )
                ),
                title=str(
                    entry.get(
                        "title",
                        "",
                    )
                ),
                hypothesis=str(
                    entry.get(
                        "hypothesis",
                        "",
                    )
                ),
                expected_outcome=str(
                    entry.get(
                        "expected_outcome",
                        "",
                    )
                ),
                status=str(
                    entry.get(
                        "status",
                        "planned",
                    )
                ),
                actual_outcome=entry.get(
                    "actual_outcome"
                ),
                result=entry.get(
                    "result"
                ),
                confidence=_clamp(
                    entry.get(
                        "confidence",
                        0.5,
                    )
                ),
                created_at=str(
                    entry.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
                started_at=entry.get(
                    "started_at"
                ),
                completed_at=entry.get(
                    "completed_at"
                ),
                observations=list(
                    entry.get(
                        "observations",
                        [],
                    )
                ),
                lessons=list(
                    entry.get(
                        "lessons",
                        [],
                    )
                ),
                metadata=dict(
                    entry.get(
                        "metadata",
                        {},
                    )
                ),
            )

            self.experiments.append(
                experiment
            )

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next experiment ID.
        """

        highest = 0

        for experiment in self.experiments:
            experiment_id = str(
                experiment.id
            )

            if not experiment_id.startswith(
                "experiment_"
            ):
                continue

            try:
                number = int(
                    experiment_id.split(
                        "_"
                    )[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return (
            f"experiment_{highest + 1}"
        )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
) -> float:
    """
    Keep a numeric value between 0.0 and 1.0.
    """

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0.5

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def _normalize(
    text: str,
) -> str:
    """
    Normalize text for basic comparison.
    """

    return " ".join(
        str(text)
        .lower()
        .strip()
        .split()
    )


def _format_outcome(
    outcome: Any,
) -> str:
    """
    Convert an experiment result into a readable string.
    """

    if isinstance(
        outcome,
        str,
    ):
        return outcome.strip()

    if outcome is None:
        return "No result returned."

    try:
        return str(
            outcome
        )
    except Exception:
        return "Result could not be represented."


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()