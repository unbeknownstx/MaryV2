"""
Mary - Autonomy Scheduler

Provides scheduling primitives for Mary's autonomy system.

The scheduler answers:

    "When should something be considered?"

It does NOT:

    - execute actions
    - execute tools
    - access the internet
    - discover capabilities
    - grant permissions
    - modify the filesystem
    - bypass approval requirements

Actual execution belongs to the autonomy runtime and the explicitly
registered systems responsible for carrying out approved actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from heapq import heappop, heappush
from time import time
from typing import Any, Callable, Mapping
from uuid import uuid4


# ================================================================
# SCHEDULE TYPES
# ================================================================


class ScheduleType(str, Enum):
    """
    Type of schedule.
    """

    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    CRON_LIKE = "cron_like"


# ================================================================
# SCHEDULE STATUS
# ================================================================


class ScheduleStatus(str, Enum):
    """
    Current schedule state.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# ================================================================
# SCHEDULE ERROR
# ================================================================


class ScheduleError(RuntimeError):
    """
    Base scheduler exception.
    """


class ScheduleValidationError(ScheduleError):
    """
    Raised when a schedule definition is invalid.
    """


# ================================================================
# SCHEDULE ENTRY
# ================================================================


@dataclass
class ScheduleEntry:
    """
    A passive description of when an autonomous item should become
    due.

    The scheduler does not execute the associated callback.
    """

    name: str

    schedule_type: ScheduleType

    next_run: float

    interval: float | None = None

    end_at: float | None = None

    max_runs: int | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    callback_key: str | None = None

    schedule_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    status: ScheduleStatus = (
        ScheduleStatus.ACTIVE
    )

    created_at: float = field(
        default_factory=time
    )

    run_count: int = 0

    last_run: float | None = None

    # ------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate this schedule.
        """

        if not self.name.strip():
            raise ScheduleValidationError(
                "Schedule name cannot be empty."
            )

        if self.next_run < 0:
            raise ScheduleValidationError(
                "next_run cannot be negative."
            )

        if (
            self.interval is not None
            and self.interval <= 0
        ):
            raise ScheduleValidationError(
                "interval must be greater than zero."
            )

        if (
            self.end_at is not None
            and self.end_at < self.next_run
        ):
            raise ScheduleValidationError(
                "end_at cannot occur before next_run."
            )

        if (
            self.max_runs is not None
            and self.max_runs < 1
        ):
            raise ScheduleValidationError(
                "max_runs must be at least 1."
            )

        if self.schedule_type == (
            ScheduleType.INTERVAL
        ):
            if self.interval is None:
                raise ScheduleValidationError(
                    "Interval schedules require an interval."
                )

    # ------------------------------------------------------------
    # Due check
    # ------------------------------------------------------------

    def is_due(
        self,
        now: float | None = None,
    ) -> bool:
        """
        Return whether the schedule is due.
        """

        current = (
            time()
            if now is None
            else now
        )

        if self.status != (
            ScheduleStatus.ACTIVE
        ):
            return False

        if (
            self.max_runs is not None
            and self.run_count
            >= self.max_runs
        ):
            return False

        if (
            self.end_at is not None
            and current > self.end_at
        ):
            return False

        return current >= self.next_run

    # ------------------------------------------------------------
    # Record run
    # ------------------------------------------------------------

    def record_run(
        self,
        when: float | None = None,
    ) -> None:
        """
        Record that the schedule became due.

        This does not execute a callback.
        """

        current = (
            time()
            if when is None
            else when
        )

        self.run_count += 1

        self.last_run = current

        if (
            self.max_runs is not None
            and self.run_count
            >= self.max_runs
        ):
            self.status = (
                ScheduleStatus.COMPLETED
            )
            return

        if self.schedule_type == (
            ScheduleType.ONCE
        ):
            self.status = (
                ScheduleStatus.COMPLETED
            )
            return

        if self.interval is not None:
            self.next_run = (
                current
                + self.interval
            )
            return

        self.status = (
            ScheduleStatus.COMPLETED
        )

    # ------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------

    def pause(self) -> None:
        """
        Pause the schedule.
        """

        if self.status == (
            ScheduleStatus.ACTIVE
        ):
            self.status = (
                ScheduleStatus.PAUSED
            )

    def resume(self) -> None:
        """
        Resume a paused schedule.
        """

        if self.status == (
            ScheduleStatus.PAUSED
        ):
            self.status = (
                ScheduleStatus.ACTIVE
            )

    def cancel(self) -> None:
        """
        Cancel the schedule.
        """

        self.status = (
            ScheduleStatus.CANCELLED
        )

    def expire(self) -> None:
        """
        Expire the schedule.
        """

        self.status = (
            ScheduleStatus.EXPIRED
        )

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "schedule_type": (
                self.schedule_type.value
            ),
            "next_run": self.next_run,
            "interval": self.interval,
            "end_at": self.end_at,
            "max_runs": self.max_runs,
            "metadata": dict(
                self.metadata
            ),
            "callback_key": self.callback_key,
            "status": self.status.value,
            "created_at": self.created_at,
            "run_count": self.run_count,
            "last_run": self.last_run,
        }


# ================================================================
# SCHEDULE EVENT
# ================================================================


@dataclass(frozen=True)
class ScheduleEvent:
    """
    Describes a schedule becoming due.

    It does not execute the associated callback.
    """

    schedule_id: str

    name: str

    timestamp: float

    run_count: int

    metadata: Mapping[
        str,
        Any,
    ]

    callback_key: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "timestamp": self.timestamp,
            "run_count": self.run_count,
            "metadata": dict(
                self.metadata
            ),
            "callback_key": self.callback_key,
        }


# ================================================================
# SCHEDULER
# ================================================================


class Scheduler:
    """
    In-memory scheduler for autonomous activity.

    The scheduler determines which schedules are due.

    It does not execute callbacks.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time,
    ) -> None:

        self._clock = clock

        self._entries: dict[
            str,
            ScheduleEntry,
        ] = {}

        self._queue: list[
            tuple[
                float,
                str,
            ]
        ] = []

    # ------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------

    def add(
        self,
        entry: ScheduleEntry,
    ) -> None:
        """
        Register a schedule.
        """

        entry.validate()

        if entry.schedule_id in self._entries:
            raise ScheduleError(
                (
                    "Schedule already exists: "
                    f"{entry.schedule_id}"
                )
            )

        self._entries[
            entry.schedule_id
        ] = entry

        heappush(
            self._queue,
            (
                entry.next_run,
                entry.schedule_id,
            ),
        )

    def remove(
        self,
        schedule_id: str,
    ) -> bool:
        """
        Remove a schedule.
        """

        if schedule_id not in self._entries:
            return False

        del self._entries[
            schedule_id
        ]

        return True

    # ------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------

    def get(
        self,
        schedule_id: str,
    ) -> ScheduleEntry | None:

        return self._entries.get(
            schedule_id
        )

    def require(
        self,
        schedule_id: str,
    ) -> ScheduleEntry:

        entry = self.get(
            schedule_id
        )

        if entry is None:
            raise ScheduleError(
                (
                    "Unknown schedule: "
                    f"{schedule_id}"
                )
            )

        return entry

    def all(
        self,
    ) -> tuple[ScheduleEntry, ...]:

        return tuple(
            self._entries.values()
        )

    # ------------------------------------------------------------
    # Due schedules
    # ------------------------------------------------------------

    def due(
        self,
        now: float | None = None,
    ) -> tuple[ScheduleEvent, ...]:
        """
        Return all schedules currently due.

        Calling this method records the schedule as having fired,
        but does not execute any associated callback.
        """

        current = (
            self._clock()
            if now is None
            else now
        )

        events: list[
            ScheduleEvent
        ] = []

        # Rebuild the heap from current entries. This keeps the
        # scheduler deterministic and avoids stale heap entries.
        self._rebuild_queue()

        while self._queue:

            next_run, schedule_id = (
                self._queue[0]
            )

            if next_run > current:
                break

            heappop(
                self._queue
            )

            entry = self._entries.get(
                schedule_id
            )

            if entry is None:
                continue

            if not entry.is_due(
                current
            ):
                continue

            entry.record_run(
                current
            )

            event = ScheduleEvent(
                schedule_id=(
                    entry.schedule_id
                ),
                name=entry.name,
                timestamp=current,
                run_count=entry.run_count,
                metadata=dict(
                    entry.metadata
                ),
                callback_key=(
                    entry.callback_key
                ),
            )

            events.append(
                event
            )

        self._rebuild_queue()

        return tuple(events)

    # ------------------------------------------------------------
    # Next schedule
    # ------------------------------------------------------------

    def next_run(
        self,
    ) -> float | None:
        """
        Return the next active scheduled timestamp.
        """

        self._rebuild_queue()

        while self._queue:

            timestamp, schedule_id = (
                self._queue[0]
            )

            entry = self._entries.get(
                schedule_id
            )

            if entry is None:
                heappop(
                    self._queue
                )
                continue

            if entry.status != (
                ScheduleStatus.ACTIVE
            ):
                heappop(
                    self._queue
                )
                continue

            return timestamp

        return None

    # ------------------------------------------------------------
    # Time until next
    # ------------------------------------------------------------

    def seconds_until_next(
        self,
    ) -> float | None:
        """
        Return seconds until the next scheduled item.
        """

        next_timestamp = (
            self.next_run()
        )

        if next_timestamp is None:
            return None

        return max(
            0.0,
            next_timestamp
            - self._clock(),
        )

    # ------------------------------------------------------------
    # Queue maintenance
    # ------------------------------------------------------------

    def _rebuild_queue(
        self,
    ) -> None:

        self._queue = [
            (
                entry.next_run,
                entry.schedule_id,
            )
            for entry
            in self._entries.values()
            if entry.status
            == ScheduleStatus.ACTIVE
        ]

        from heapq import heapify

        heapify(
            self._queue
        )

    # ------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------

    def pause(
        self,
        schedule_id: str,
    ) -> None:

        self.require(
            schedule_id
        ).pause()

        self._rebuild_queue()

    def resume(
        self,
        schedule_id: str,
    ) -> None:

        self.require(
            schedule_id
        ).resume()

        self._rebuild_queue()

    def cancel(
        self,
        schedule_id: str,
    ) -> None:

        self.require(
            schedule_id
        ).cancel()

        self._rebuild_queue()

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_list(
        self,
    ) -> list[dict[str, Any]]:

        return [
            entry.to_dict()
            for entry
            in self._entries.values()
        ]


# ================================================================
# FACTORIES
# ================================================================


def create_one_time_schedule(
    name: str,
    run_at: float,
    *,
    metadata: Mapping[
        str,
        Any,
    ]
    | None = None,
    callback_key: str | None = None,
) -> ScheduleEntry:
    """
    Create a one-time schedule.
    """

    entry = ScheduleEntry(
        name=name,
        schedule_type=ScheduleType.ONCE,
        next_run=run_at,
        metadata=dict(
            metadata
            if metadata is not None
            else {}
        ),
        callback_key=callback_key,
    )

    entry.validate()

    return entry


def create_interval_schedule(
    name: str,
    first_run: float,
    interval: float,
    *,
    max_runs: int | None = None,
    end_at: float | None = None,
    metadata: Mapping[
        str,
        Any,
    ]
    | None = None,
    callback_key: str | None = None,
) -> ScheduleEntry:
    """
    Create a recurring interval schedule.
    """

    entry = ScheduleEntry(
        name=name,
        schedule_type=(
            ScheduleType.INTERVAL
        ),
        next_run=first_run,
        interval=interval,
        max_runs=max_runs,
        end_at=end_at,
        metadata=dict(
            metadata
            if metadata is not None
            else {}
        ),
        callback_key=callback_key,
    )

    entry.validate()

    return entry


# ================================================================
# EXPORTS
# ================================================================


__all__ = [
    "ScheduleEntry",
    "ScheduleError",
    "ScheduleEvent",
    "ScheduleStatus",
    "ScheduleType",
    "ScheduleValidationError",
    "Scheduler",
    "create_interval_schedule",
    "create_one_time_schedule",
]