"""
MaryV2 - Learning Coordinator

Coordinates Mary's learning process.

The learner does not directly browse the web, modify code, or
execute experiments. Those responsibilities belong to the
researcher, evaluator, knowledge, and experiment systems.

Architecture:

    Experience / Research / Feedback
                  ↓
               Learner
                  ↓
        ┌─────────┼─────────┐
        ↓         ↓         ↓
     Evaluate   Store     Reflect
        ↓         ↓         ↓
      Knowledge / Memory / Agency
"""


from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mary.governance.bounds import bounded_payload, clip_text


# ================================================================
# LEARNING EVENT
# ================================================================


@dataclass
class LearningEvent:
    """
    Represents something Mary can learn from.
    """

    id: str

    event_type: str

    subject: str

    content: str

    source: str | None = None

    confidence: float = 0.5

    usefulness: float = 0.5

    status: str = "new"

    created_at: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()

        self.confidence = _clamp(
            self.confidence
        )

        self.usefulness = _clamp(
            self.usefulness
        )


# ================================================================
# LEARNER
# ================================================================


class Learner:
    """
    Mary's learning coordinator.

    This system tracks learning events and determines which
    information is worth passing to other systems.

    It intentionally does not assume that every piece of new
    information should become permanent knowledge.
    """

    def __init__(self, *, capacity: int = 512, text_limit: int = 4000) -> None:
        self.events: list[LearningEvent] = []
        self.capacity = max(1, int(capacity))
        self.text_limit = max(256, int(text_limit))

    def _trim(self) -> None:
        del self.events[:-self.capacity]

    # ============================================================
    # RECORD
    # ============================================================

    def record(
        self,
        event_type: str,
        subject: str,
        content: str,
        *,
        source: str | None = None,
        confidence: float = 0.5,
        usefulness: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> LearningEvent:
        """
        Record a new learning event.
        """

        event = LearningEvent(
            id=self._next_id(),
            event_type=clip_text(event_type, 160),
            subject=clip_text(subject, self.text_limit),
            content=clip_text(content, self.text_limit),
            source=source,
            confidence=confidence,
            usefulness=usefulness,
            metadata=bounded_payload(metadata or {}, text_limit=self.text_limit),
        )

        self.events.append(event)
        self._trim()

        return event

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        event_id: str,
    ) -> LearningEvent | None:
        """
        Retrieve a learning event by ID.
        """

        for event in self.events:
            if event.id == event_id:
                return event

        return None

    def get_all(self) -> list[LearningEvent]:
        """
        Return all learning events.
        """

        return list(
            self.events
        )

    def get_recent(
        self,
        count: int = 10,
    ) -> list[LearningEvent]:
        """
        Return the most recent learning events.
        """

        if count <= 0:
            return []

        return self.events[-count:]

    # ============================================================
    # EVALUATION SUPPORT
    # ============================================================

    def mark_evaluated(
        self,
        event_id: str,
        *,
        confidence: float | None = None,
        usefulness: float | None = None,
    ) -> bool:
        """
        Mark a learning event as evaluated.
        """

        event = self.get(
            event_id
        )

        if event is None:
            return False

        if confidence is not None:
            event.confidence = _clamp(
                confidence
            )

        if usefulness is not None:
            event.usefulness = _clamp(
                usefulness
            )

        event.status = "evaluated"

        return True

    # ============================================================
    # ACCEPTANCE
    # ============================================================

    def accept(
        self,
        event_id: str,
    ) -> bool:
        """
        Mark a learning event as accepted as useful information.

        This does not automatically write it into permanent
        knowledge. The knowledge system owns that responsibility.
        """

        event = self.get(
            event_id
        )

        if event is None:
            return False

        event.status = "accepted"

        return True

    def reject(
        self,
        event_id: str,
    ) -> bool:
        """
        Reject a learning event.
        """

        event = self.get(
            event_id
        )

        if event is None:
            return False

        event.status = "rejected"

        return True

    # ============================================================
    # USEFUL INFORMATION
    # ============================================================

    def get_accepted(
        self,
    ) -> list[LearningEvent]:
        """
        Return learning events accepted as useful.
        """

        return [
            event
            for event in self.events
            if event.status == "accepted"
        ]

    def get_high_value(
        self,
        minimum_confidence: float = 0.7,
        minimum_usefulness: float = 0.7,
    ) -> list[LearningEvent]:
        """
        Return learning events with strong confidence and
        usefulness scores.
        """

        return [
            event
            for event in self.events
            if (
                event.confidence
                >= minimum_confidence
                and event.usefulness
                >= minimum_usefulness
            )
        ]

    # ============================================================
    # LEARNING SUMMARY
    # ============================================================

    def summarize(
        self,
    ) -> dict[str, Any]:
        """
        Return a summary of Mary's learning activity.
        """

        total = len(
            self.events
        )

        accepted = len(
            [
                event
                for event in self.events
                if event.status == "accepted"
            ]
        )

        rejected = len(
            [
                event
                for event in self.events
                if event.status == "rejected"
            ]
        )

        evaluated = len(
            [
                event
                for event in self.events
                if event.status == "evaluated"
            ]
        )

        average_confidence = 0.0
        average_usefulness = 0.0

        if total:
            average_confidence = (
                sum(
                    event.confidence
                    for event in self.events
                )
                / total
            )

            average_usefulness = (
                sum(
                    event.usefulness
                    for event in self.events
                )
                / total
            )

        return {
            "total_events": total,
            "evaluated": evaluated,
            "accepted": accepted,
            "rejected": rejected,
            "average_confidence": (
                average_confidence
            ),
            "average_usefulness": (
                average_usefulness
            ),
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> list[dict[str, Any]]:
        """
        Convert learning history into serializable dictionaries.
        """

        return [
            {
                "id": event.id,
                "event_type": event.event_type,
                "subject": event.subject,
                "content": event.content,
                "source": event.source,
                "confidence": event.confidence,
                "usefulness": event.usefulness,
                "status": event.status,
                "created_at": event.created_at,
                "metadata": event.metadata,
            }
            for event in self.events
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore learning history.
        """

        self.events.clear()

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

            event = LearningEvent(
                id=str(
                    entry.get(
                        "id",
                        "",
                    )
                ),
                event_type=str(
                    entry.get(
                        "event_type",
                        "unknown",
                    )
                ),
                subject=str(
                    entry.get(
                        "subject",
                        "",
                    )
                ),
                content=str(
                    entry.get(
                        "content",
                        "",
                    )
                ),
                source=entry.get(
                    "source"
                ),
                confidence=_clamp(
                    entry.get(
                        "confidence",
                        0.5,
                    )
                ),
                usefulness=_clamp(
                    entry.get(
                        "usefulness",
                        0.5,
                    )
                ),
                status=str(
                    entry.get(
                        "status",
                        "new",
                    )
                ),
                created_at=str(
                    entry.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
                metadata=entry.get(
                    "metadata",
                    {},
                ),
            )

            self.events.append(event)

        self._trim()

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next learning event ID.
        """

        highest = 0

        for event in self.events:
            event_id = str(
                event.id
            )

            if not event_id.startswith(
                "learning_"
            ):
                continue

            try:
                number = int(
                    event_id.split(
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
            f"learning_{highest + 1}"
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


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()