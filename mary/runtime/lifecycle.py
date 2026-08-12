"""
MaryV2 - Runtime Lifecycle

Controls initialization, startup, pausing, stopping, and shutdown
of explicitly supplied runtime subsystems.

This module does NOT:

    - discover subsystems automatically
    - access the internet
    - select external providers
    - request API credentials
    - access hardware without an explicitly supplied subsystem
    - create tools
    - modify subsystem internals

The lifecycle layer coordinates components. It does not own their
business logic.

Architecture:

    RuntimeLifecycle
          |
          +--> RuntimeState
          |
          +--> subsystem adapters
"""


from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, Iterable, Mapping

from .state import (
    RuntimeState,
    RuntimeStatus,
    SubsystemState,
    SubsystemStatus,
)


# ================================================================
# LIFECYCLE STATUS
# ================================================================


class LifecycleStatus(str, Enum):
    """
    Result state of a lifecycle operation.
    """

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


# ================================================================
# LIFECYCLE ERRORS
# ================================================================


class LifecycleError(
    RuntimeError
):
    """
    Base exception for lifecycle failures.
    """


class LifecycleInitializationError(
    LifecycleError
):
    """
    Raised when subsystem initialization fails.
    """


class LifecycleStartError(
    LifecycleError
):
    """
    Raised when subsystem startup fails.
    """


class LifecyclePauseError(
    LifecycleError
):
    """
    Raised when pausing fails.
    """


class LifecycleStopError(
    LifecycleError
):
    """
    Raised when stopping fails.
    """


class LifecycleShutdownError(
    LifecycleError
):
    """
    Raised when shutdown fails.
    """


# ================================================================
# LIFECYCLE RESULT
# ================================================================


@dataclass
class LifecycleResult:
    """
    Describes the result of one lifecycle operation.
    """

    operation: str

    status: LifecycleStatus

    succeeded: list[str] = field(
        default_factory=list
    )

    failed: list[str] = field(
        default_factory=list
    )

    skipped: list[str] = field(
        default_factory=list
    )

    errors: dict[str, str] = field(
        default_factory=dict
    )

    started_at: float = field(
        default_factory=time
    )

    completed_at: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def successful(
        self,
    ) -> bool:
        return (
            self.status
            == LifecycleStatus.SUCCESS
        )

    @property
    def partial(
        self,
    ) -> bool:
        return (
            self.status
            == LifecycleStatus.PARTIAL
        )

    @property
    def failed_operation(
        self,
    ) -> bool:
        return (
            self.status
            == LifecycleStatus.FAILED
        )

    @property
    def elapsed(
        self,
    ) -> float | None:
        if self.completed_at is None:
            return None

        return max(
            0.0,
            self.completed_at
            - self.started_at,
        )

    @property
    def total_processed(
        self,
    ) -> int:
        return (
            len(self.succeeded)
            + len(self.failed)
            + len(self.skipped)
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "status": self.status.value,
            "succeeded": list(
                self.succeeded
            ),
            "failed": list(
                self.failed
            ),
            "skipped": list(
                self.skipped
            ),
            "errors": dict(
                self.errors
            ),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed": self.elapsed,
            "total_processed": (
                self.total_processed
            ),
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# LIFECYCLE CONTEXT
# ================================================================


@dataclass
class LifecycleContext:
    """
    Context passed to lifecycle-aware subsystem adapters.

    It provides shared runtime information without giving the
    subsystem unrestricted control over the runtime.
    """

    runtime_state: RuntimeState

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        return self.metadata.get(
            key,
            default,
        )


# ================================================================
# SUBSYSTEM ADAPTER
# ================================================================


class SubsystemLifecycleAdapter(
    ABC
):
    """
    Abstract lifecycle interface for a runtime subsystem.

    Each subsystem can implement the lifecycle methods it actually
    needs.

    The runtime lifecycle manager calls these methods explicitly.
    """

    name: str

    version: str | None = None

    required: bool = False

    enabled: bool = True

    # ============================================================
    # INITIALIZE
    # ============================================================

    def initialize(
        self,
        context: LifecycleContext,
    ) -> None:
        """
        Prepare the subsystem.

        Default implementation does nothing.
        """

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        context: LifecycleContext,
    ) -> None:
        """
        Start active subsystem behavior.

        Default implementation does nothing.
        """

    # ============================================================
    # PAUSE
    # ============================================================

    def pause(
        self,
        context: LifecycleContext,
    ) -> None:
        """
        Pause subsystem activity.

        Default implementation does nothing.
        """

    # ============================================================
    # RESUME
    # ============================================================

    def resume(
        self,
        context: LifecycleContext,
    ) -> None:
        """
        Resume subsystem activity.

        Default implementation does nothing.
        """

    # ============================================================
    # STOP
    # ============================================================

    def stop(
        self,
        context: LifecycleContext,
    ) -> None:
        """
        Stop active subsystem behavior.

        Default implementation does nothing.
        """

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(
        self,
        context: LifecycleContext,
    ) -> None:
        """
        Release subsystem resources.

        Default implementation does nothing.
        """

    # ============================================================
    # HEALTH
    # ============================================================

    def health(
        self,
    ) -> Mapping[str, Any]:
        """
        Optional subsystem health information.
        """

        return {}


# ================================================================
# CALLBACK ADAPTER
# ================================================================


@dataclass
class CallbackSubsystem(
    SubsystemLifecycleAdapter
):
    """
    Lightweight adapter for subsystems that only need callbacks.

    This allows the runtime to integrate existing components without
    forcing them to inherit from SubsystemLifecycleAdapter.
    """

    name: str

    version: str | None = None

    required: bool = False

    enabled: bool = True

    initialize_callback: Callable[
        [LifecycleContext],
        None,
    ] | None = None

    start_callback: Callable[
        [LifecycleContext],
        None,
    ] | None = None

    pause_callback: Callable[
        [LifecycleContext],
        None,
    ] | None = None

    resume_callback: Callable[
        [LifecycleContext],
        None,
    ] | None = None

    stop_callback: Callable[
        [LifecycleContext],
        None,
    ] | None = None

    shutdown_callback: Callable[
        [LifecycleContext],
        None,
    ] | None = None

    health_callback: Callable[
        [],
        Mapping[str, Any],
    ] | None = None

    def initialize(
        self,
        context: LifecycleContext,
    ) -> None:

        if self.initialize_callback is not None:
            self.initialize_callback(
                context
            )

    def start(
        self,
        context: LifecycleContext,
    ) -> None:

        if self.start_callback is not None:
            self.start_callback(
                context
            )

    def pause(
        self,
        context: LifecycleContext,
    ) -> None:

        if self.pause_callback is not None:
            self.pause_callback(
                context
            )

    def resume(
        self,
        context: LifecycleContext,
    ) -> None:

        if self.resume_callback is not None:
            self.resume_callback(
                context
            )

    def stop(
        self,
        context: LifecycleContext,
    ) -> None:

        if self.stop_callback is not None:
            self.stop_callback(
                context
            )

    def shutdown(
        self,
        context: LifecycleContext,
    ) -> None:

        if self.shutdown_callback is not None:
            self.shutdown_callback(
                context
            )

    def health(
        self,
    ) -> Mapping[str, Any]:

        if self.health_callback is None:
            return {}

        return dict(
            self.health_callback()
        )


# ================================================================
# RUNTIME LIFECYCLE
# ================================================================


class RuntimeLifecycle:
    """
    Coordinates the lifecycle of explicitly registered subsystems.

    Subsystems are supplied by the application. Nothing is
    automatically discovered.
    """

    def __init__(
        self,
        runtime_state: RuntimeState | None = None,
        *,
        context_metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        self.state = (
            runtime_state
            if runtime_state is not None
            else RuntimeState()
        )

        self.context = LifecycleContext(
            runtime_state=self.state,
            metadata=dict(
                context_metadata
                if context_metadata is not None
                else {}
            ),
        )

        self._subsystems: dict[
            str,
            SubsystemLifecycleAdapter,
        ] = {}

    # ============================================================
    # REGISTRATION
    # ============================================================

    def register(
        self,
        subsystem: SubsystemLifecycleAdapter,
    ) -> SubsystemState:
        """
        Register an explicitly supplied subsystem adapter.

        Registration does not initialize or start the subsystem.
        """

        if not isinstance(
            subsystem,
            SubsystemLifecycleAdapter,
        ):
            raise TypeError(
                "subsystem must implement "
                "SubsystemLifecycleAdapter."
            )

        name = str(
            subsystem.name
        ).strip()

        if not name:
            raise ValueError(
                "Subsystem name cannot be empty."
            )

        if name in self._subsystems:
            raise ValueError(
                f"Subsystem already registered: {name}"
            )

        self._subsystems[name] = subsystem

        existing = (
            self.state.get_subsystem(
                name
            )
        )

        if existing is None:
            existing = (
                self.state.register_subsystem(
                    name,
                    enabled=subsystem.enabled,
                    required=subsystem.required,
                    version=subsystem.version,
                )
            )
        else:
            existing.enabled = (
                subsystem.enabled
            )

            existing.required = (
                subsystem.required
            )

            existing.version = (
                subsystem.version
            )

            if not subsystem.enabled:
                existing.status = (
                    SubsystemStatus.DISABLED
                )

        return existing

    def unregister(
        self,
        name: str,
    ) -> bool:
        """
        Remove a registered adapter.

        This does not call shutdown automatically.
        """

        removed = (
            self._subsystems.pop(
                name,
                None,
            )
            is not None
        )

        return removed

    # ============================================================
    # ACCESS
    # ============================================================

    def get(
        self,
        name: str,
    ) -> SubsystemLifecycleAdapter | None:
        return self._subsystems.get(
            name
        )

    @property
    def subsystem_names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._subsystems.keys()
        )

    # ============================================================
    # INITIALIZE
    # ============================================================

    def initialize(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Initialize all enabled registered subsystems.

        Initialization happens in registration order.
        """

        self.state.status = (
            RuntimeStatus.INITIALIZING
        )

        result = LifecycleResult(
            operation="initialize",
            status=LifecycleStatus.SUCCESS,
        )

        for name, subsystem in (
            self._subsystems.items()
        ):

            state = self.state.require_subsystem(
                name
            )

            if not subsystem.enabled:
                state.status = (
                    SubsystemStatus.DISABLED
                )

                result.skipped.append(
                    name
                )

                continue

            state.mark_initializing()

            try:
                subsystem.initialize(
                    self.context
                )

                state.mark_ready()

                result.succeeded.append(
                    name
                )

            except Exception as exc:
                state.mark_error(
                    str(exc)
                )

                result.failed.append(
                    name
                )

                result.errors[name] = str(
                    exc
                )

                if (
                    raise_on_error
                    and state.required
                ):
                    result.status = (
                        LifecycleStatus.FAILED
                    )

                    result.completed_at = time()

                    self.state.set_error(
                        str(exc)
                    )

                    raise LifecycleInitializationError(
                        (
                            f"Failed to initialize "
                            f"required subsystem "
                            f"'{name}': {exc}"
                        )
                    ) from exc

        result.completed_at = time()

        self._finalize_result(
            result
        )

        if result.successful:
            self.state.status = (
                RuntimeStatus.READY
            )

        elif result.partial:
            self.state.status = (
                RuntimeStatus.READY
            )

        else:
            self.state.status = (
                RuntimeStatus.ERROR
            )

        return result

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Start initialized subsystems.
        """

        result = LifecycleResult(
            operation="start",
            status=LifecycleStatus.SUCCESS,
        )

        for name, subsystem in (
            self._subsystems.items()
        ):

            state = self.state.require_subsystem(
                name
            )

            if not subsystem.enabled:
                result.skipped.append(
                    name
                )

                continue

            if state.status not in {
                SubsystemStatus.READY,
                SubsystemStatus.PAUSED,
            }:
                result.skipped.append(
                    name
                )

                continue

            try:
                if (
                    state.status
                    == SubsystemStatus.PAUSED
                ):
                    subsystem.resume(
                        self.context
                    )
                else:
                    subsystem.start(
                        self.context
                    )

                state.mark_running()

                result.succeeded.append(
                    name
                )

            except Exception as exc:
                state.mark_error(
                    str(exc)
                )

                result.failed.append(
                    name
                )

                result.errors[name] = str(
                    exc
                )

                if (
                    raise_on_error
                    and state.required
                ):
                    result.status = (
                        LifecycleStatus.FAILED
                    )

                    result.completed_at = time()

                    self.state.set_error(
                        str(exc)
                    )

                    raise LifecycleStartError(
                        (
                            f"Failed to start "
                            f"required subsystem "
                            f"'{name}': {exc}"
                        )
                    ) from exc

        result.completed_at = time()

        self._finalize_result(
            result
        )

        if result.failed_operation:
            self.state.status = (
                RuntimeStatus.ERROR
            )
        else:
            self.state.status = (
                RuntimeStatus.RUNNING
            )

            self.state.started_at = time()

        return result

    # ============================================================
    # PAUSE
    # ============================================================

    def pause(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Pause running subsystems.
        """

        self.state.status = (
            RuntimeStatus.PAUSING
        )

        result = LifecycleResult(
            operation="pause",
            status=LifecycleStatus.SUCCESS,
        )

        for name, subsystem in (
            self._subsystems.items()
        ):

            state = self.state.require_subsystem(
                name
            )

            if not subsystem.enabled:
                result.skipped.append(
                    name
                )

                continue

            if (
                state.status
                != SubsystemStatus.RUNNING
            ):
                result.skipped.append(
                    name
                )

                continue

            try:
                subsystem.pause(
                    self.context
                )

                state.mark_paused()

                result.succeeded.append(
                    name
                )

            except Exception as exc:
                state.mark_error(
                    str(exc)
                )

                result.failed.append(
                    name
                )

                result.errors[name] = str(
                    exc
                )

                if (
                    raise_on_error
                    and state.required
                ):
                    result.status = (
                        LifecycleStatus.FAILED
                    )

                    result.completed_at = time()

                    self.state.set_error(
                        str(exc)
                    )

                    raise LifecyclePauseError(
                        (
                            f"Failed to pause "
                            f"required subsystem "
                            f"'{name}': {exc}"
                        )
                    ) from exc

        result.completed_at = time()

        self._finalize_result(
            result
        )

        if result.failed_operation:
            self.state.status = (
                RuntimeStatus.ERROR
            )
        else:
            self.state.status = (
                RuntimeStatus.PAUSED
            )

        return result

    # ============================================================
    # RESUME
    # ============================================================

    def resume(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Resume paused subsystems.
        """

        result = LifecycleResult(
            operation="resume",
            status=LifecycleStatus.SUCCESS,
        )

        for name, subsystem in (
            self._subsystems.items()
        ):

            state = self.state.require_subsystem(
                name
            )

            if not subsystem.enabled:
                result.skipped.append(
                    name
                )

                continue

            if (
                state.status
                != SubsystemStatus.PAUSED
            ):
                result.skipped.append(
                    name
                )

                continue

            try:
                subsystem.resume(
                    self.context
                )

                state.mark_running()

                result.succeeded.append(
                    name
                )

            except Exception as exc:
                state.mark_error(
                    str(exc)
                )

                result.failed.append(
                    name
                )

                result.errors[name] = str(
                    exc
                )

                if (
                    raise_on_error
                    and state.required
                ):
                    result.status = (
                        LifecycleStatus.FAILED
                    )

                    result.completed_at = time()

                    self.state.set_error(
                        str(exc)
                    )

                    raise LifecycleError(
                        (
                            f"Failed to resume "
                            f"required subsystem "
                            f"'{name}': {exc}"
                        )
                    ) from exc

        result.completed_at = time()

        self._finalize_result(
            result
        )

        if result.failed_operation:
            self.state.status = (
                RuntimeStatus.ERROR
            )
        else:
            self.state.status = (
                RuntimeStatus.RUNNING
            )

        return result

    # ============================================================
    # STOP
    # ============================================================

    def stop(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Stop active subsystems.

        Subsystems are stopped in reverse registration order.
        """

        self.state.status = (
            RuntimeStatus.STOPPING
        )

        result = LifecycleResult(
            operation="stop",
            status=LifecycleStatus.SUCCESS,
        )

        registered = list(
            self._subsystems.items()
        )

        registered.reverse()

        for name, subsystem in registered:

            state = self.state.require_subsystem(
                name
            )

            if not subsystem.enabled:
                result.skipped.append(
                    name
                )

                continue

            if state.status not in {
                SubsystemStatus.RUNNING,
                SubsystemStatus.PAUSED,
                SubsystemStatus.READY,
            }:
                result.skipped.append(
                    name
                )

                continue

            try:
                subsystem.stop(
                    self.context
                )

                state.mark_stopped()

                result.succeeded.append(
                    name
                )

            except Exception as exc:
                state.mark_error(
                    str(exc)
                )

                result.failed.append(
                    name
                )

                result.errors[name] = str(
                    exc
                )

                if (
                    raise_on_error
                    and state.required
                ):
                    result.status = (
                        LifecycleStatus.FAILED
                    )

                    result.completed_at = time()

                    self.state.set_error(
                        str(exc)
                    )

                    raise LifecycleStopError(
                        (
                            f"Failed to stop "
                            f"required subsystem "
                            f"'{name}': {exc}"
                        )
                    ) from exc

        result.completed_at = time()

        self._finalize_result(
            result
        )

        if result.failed_operation:
            self.state.status = (
                RuntimeStatus.ERROR
            )
        else:
            self.state.status = (
                RuntimeStatus.STOPPED
            )

            self.state.stopped_at = time()

        return result

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Fully shut down all registered subsystems.

        Shutdown occurs in reverse registration order.
        """

        result = LifecycleResult(
            operation="shutdown",
            status=LifecycleStatus.SUCCESS,
        )

        registered = list(
            self._subsystems.items()
        )

        registered.reverse()

        for name, subsystem in registered:

            state = self.state.require_subsystem(
                name
            )

            if not subsystem.enabled:
                result.skipped.append(
                    name
                )

                continue

            if state.status in {
                SubsystemStatus.STOPPED,
                SubsystemStatus.DISABLED,
                SubsystemStatus.UNKNOWN,
            }:
                result.skipped.append(
                    name
                )

                continue

            try:
                subsystem.shutdown(
                    self.context
                )

                state.mark_stopped()

                result.succeeded.append(
                    name
                )

            except Exception as exc:
                state.mark_error(
                    str(exc)
                )

                result.failed.append(
                    name
                )

                result.errors[name] = str(
                    exc
                )

                if (
                    raise_on_error
                    and state.required
                ):
                    result.status = (
                        LifecycleStatus.FAILED
                    )

                    result.completed_at = time()

                    self.state.set_error(
                        str(exc)
                    )

                    raise LifecycleShutdownError(
                        (
                            f"Failed to shut down "
                            f"required subsystem "
                            f"'{name}': {exc}"
                        )
                    ) from exc

        result.completed_at = time()

        self._finalize_result(
            result
        )

        if result.failed_operation:
            self.state.status = (
                RuntimeStatus.ERROR
            )
        else:
            self.state.status = (
                RuntimeStatus.STOPPED
            )

            self.state.stopped_at = time()

        return result

    # ============================================================
    # HEALTH
    # ============================================================

    def health(
        self,
    ) -> dict[str, Mapping[str, Any]]:
        """
        Collect optional health information from registered
        subsystems.

        Health checks are explicit and only call adapters that have
        been supplied to the lifecycle manager.
        """

        result: dict[
            str,
            Mapping[str, Any],
        ] = {}

        for name, subsystem in (
            self._subsystems.items()
        ):
            try:
                result[name] = dict(
                    subsystem.health()
                )
            except Exception as exc:
                result[name] = {
                    "status": "error",
                    "error": str(exc),
                }

        return result

    # ============================================================
    # INTERNAL RESULT HANDLING
    # ============================================================

    def _finalize_result(
        self,
        result: LifecycleResult,
    ) -> None:
        """
        Determine final result status.
        """

        if result.failed:
            if result.succeeded:
                result.status = (
                    LifecycleStatus.PARTIAL
                )
            else:
                result.status = (
                    LifecycleStatus.FAILED
                )

        elif result.succeeded:
            result.status = (
                LifecycleStatus.SUCCESS
            )

        else:
            result.status = (
                LifecycleStatus.SKIPPED
            )


# ================================================================
# SIMPLE LIFECYCLE ADAPTER
# ================================================================


class BasicSubsystem(
    SubsystemLifecycleAdapter
):
    """
    Minimal no-op subsystem useful for testing the runtime
    lifecycle.

    It intentionally performs no external work.
    """

    def __init__(
        self,
        name: str,
        *,
        required: bool = False,
        enabled: bool = True,
        version: str | None = None,
    ) -> None:

        self.name = name

        self.required = required

        self.enabled = enabled

        self.version = version

        self.initialized = False

        self.running = False

        self.paused = False

    def initialize(
        self,
        context: LifecycleContext,
    ) -> None:

        self.initialized = True

    def start(
        self,
        context: LifecycleContext,
    ) -> None:

        if not self.initialized:
            raise LifecycleStartError(
                (
                    f"Subsystem '{self.name}' "
                    "has not been initialized."
                )
            )

        self.running = True
        self.paused = False

    def pause(
        self,
        context: LifecycleContext,
    ) -> None:

        if not self.running:
            return

        self.running = False
        self.paused = True

    def resume(
        self,
        context: LifecycleContext,
    ) -> None:

        if not self.initialized:
            raise LifecycleError(
                (
                    f"Subsystem '{self.name}' "
                    "has not been initialized."
                )
            )

        self.running = True
        self.paused = False

    def stop(
        self,
        context: LifecycleContext,
    ) -> None:

        self.running = False
        self.paused = False

    def shutdown(
        self,
        context: LifecycleContext,
    ) -> None:

        self.running = False
        self.paused = False
        self.initialized = False

    def health(
        self,
    ) -> Mapping[str, Any]:

        return {
            "initialized": self.initialized,
            "running": self.running,
            "paused": self.paused,
        }


# ================================================================
# FACTORY
# ================================================================


def create_runtime_lifecycle(
    runtime_state: RuntimeState | None = None,
    *,
    subsystems: Iterable[
        SubsystemLifecycleAdapter
    ]
    | None = None,
    context_metadata: Mapping[
        str,
        Any,
    ]
    | None = None,
) -> RuntimeLifecycle:
    """
    Create a RuntimeLifecycle with explicitly supplied subsystems.

    No subsystem is automatically discovered or initialized.
    """

    lifecycle = RuntimeLifecycle(
        runtime_state,
        context_metadata=context_metadata,
    )

    if subsystems is not None:
        for subsystem in subsystems:
            lifecycle.register(
                subsystem
            )

    return lifecycle