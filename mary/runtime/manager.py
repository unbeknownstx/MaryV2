"""
MaryV2 - Runtime Manager

Top-level coordinator for Mary's runtime.

Responsibilities:

    - Own the runtime lifecycle
    - Own the main processing pipeline
    - Register explicitly supplied subsystems
    - Start and stop the runtime
    - Submit individual turns to the pipeline
    - Expose runtime status and health

This module does NOT:

    - Automatically discover tools
    - Automatically enable internet access
    - Select an LLM provider
    - Create API clients
    - Access hardware
    - Modify subsystem internals
    - Decide what capabilities Mary has

All capabilities must be explicitly supplied by the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .lifecycle import (
    LifecycleResult,
    RuntimeLifecycle,
    SubsystemLifecycleAdapter,
)
from .pipeline import (
    Pipeline,
    PipelineResult,
    PipelineStage,
)
from .state import RuntimeState


# ================================================================
# RUNTIME MANAGER STATUS
# ================================================================


class ManagerStatus(str, Enum):
    """
    High-level runtime manager state.
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ================================================================
# RUNTIME MANAGER ERROR
# ================================================================


class RuntimeManagerError(RuntimeError):
    """
    Base exception for runtime manager failures.
    """


# ================================================================
# RUNTIME SNAPSHOT
# ================================================================


@dataclass
class RuntimeSnapshot:
    """
    Point-in-time summary of the runtime.
    """

    status: ManagerStatus

    initialized: bool

    running: bool

    paused: bool

    subsystem_names: tuple[str, ...]

    pipeline_stages: tuple[str, ...]

    turn_count: int

    last_error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "initialized": self.initialized,
            "running": self.running,
            "paused": self.paused,
            "subsystems": list(
                self.subsystem_names
            ),
            "pipeline_stages": list(
                self.pipeline_stages
            ),
            "turn_count": self.turn_count,
            "last_error": self.last_error,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# RUNTIME MANAGER
# ================================================================


class RuntimeManager:
    """
    Top-level coordinator for Mary's runtime.

    The manager connects lifecycle management and pipeline
    execution without owning the logic of individual subsystems.
    """

    def __init__(
        self,
        *,
        runtime_state: RuntimeState | None = None,
        lifecycle: RuntimeLifecycle | None = None,
        pipeline: Pipeline | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        # --------------------------------------------------------
        # Runtime state
        # --------------------------------------------------------

        if runtime_state is not None:
            self.state = runtime_state

        elif lifecycle is not None:
            self.state = lifecycle.state

        elif pipeline is not None:
            self.state = pipeline.runtime_state

        else:
            self.state = RuntimeState()

        # --------------------------------------------------------
        # Lifecycle
        # --------------------------------------------------------

        if lifecycle is not None:

            if lifecycle.state is not self.state:
                raise RuntimeManagerError(
                    (
                        "Lifecycle and runtime state "
                        "must reference the same RuntimeState."
                    )
                )

            self.lifecycle = lifecycle

        else:
            self.lifecycle = RuntimeLifecycle(
                self.state,
                context_metadata=metadata,
            )

        # --------------------------------------------------------
        # Pipeline
        # --------------------------------------------------------

        if pipeline is not None:

            if pipeline.runtime_state is not self.state:
                raise RuntimeManagerError(
                    (
                        "Pipeline and runtime state "
                        "must reference the same RuntimeState."
                    )
                )

            self.pipeline = pipeline

        else:
            self.pipeline = Pipeline(
                self.state
            )

        # --------------------------------------------------------
        # Manager state
        # --------------------------------------------------------

        self._status = (
            ManagerStatus.CREATED
        )

        self._initialized = False

        self._running = False

        self._paused = False

        self._last_error: str | None = None

        self._metadata: dict[
            str,
            Any,
        ] = dict(
            metadata
            if metadata is not None
            else {}
        )

    # ============================================================
    # SUBSYSTEM REGISTRATION
    # ============================================================

    def register_subsystem(
        self,
        subsystem: SubsystemLifecycleAdapter,
    ) -> None:
        """
        Explicitly register a runtime subsystem.

        Registration does not initialize or start it.
        """

        if self._initialized:
            raise RuntimeManagerError(
                (
                    "Subsystems cannot be registered "
                    "after runtime initialization."
                )
            )

        self.lifecycle.register(
            subsystem
        )

    def register_subsystems(
        self,
        subsystems: Iterable[
            SubsystemLifecycleAdapter
        ],
    ) -> None:
        """
        Register multiple explicitly supplied subsystems.
        """

        for subsystem in subsystems:
            self.register_subsystem(
                subsystem
            )

    # ============================================================
    # PIPELINE REGISTRATION
    # ============================================================

    def add_stage(
        self,
        stage: PipelineStage,
    ) -> None:
        """
        Add an explicitly supplied processing stage.

        Pipeline stages cannot be added while the runtime is active.
        """

        if self._running:
            raise RuntimeManagerError(
                (
                    "Pipeline stages cannot be "
                    "modified while the runtime is running."
                )
            )

        self.pipeline.add_stage(
            stage
        )

    def remove_stage(
        self,
        name: str,
    ) -> bool:
        """
        Remove a pipeline stage.
        """

        if self._running:
            raise RuntimeManagerError(
                (
                    "Pipeline stages cannot be "
                    "modified while the runtime is running."
                )
            )

        return self.pipeline.remove_stage(
            name
        )

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def initialize(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Initialize the runtime and all explicitly registered
        subsystems.
        """

        if self._initialized:
            return LifecycleResult(
                operation="initialize",
                status=(
                    self._lifecycle_status_success()
                ),
                skipped=list(
                    self.lifecycle.subsystem_names
                ),
            )

        self._status = (
            ManagerStatus.INITIALIZING
        )

        try:

            validation_errors = (
                self.pipeline.validate()
            )

            if validation_errors:
                message = "; ".join(
                    validation_errors
                )

                self._last_error = message

                self._status = (
                    ManagerStatus.ERROR
                )

                raise RuntimeManagerError(
                    message
                )

            result = self.lifecycle.initialize(
                raise_on_error=raise_on_error
            )

            if result.failed_operation:

                self._status = (
                    ManagerStatus.ERROR
                )

                self._last_error = (
                    "Runtime initialization failed."
                )

            else:

                self._initialized = True

                self._status = (
                    ManagerStatus.READY
                )

            return result

        except Exception as exc:

            self._last_error = str(
                exc
            )

            self._status = (
                ManagerStatus.ERROR
            )

            if raise_on_error:
                raise

            return LifecycleResult(
                operation="initialize",
                status=(
                    self._lifecycle_status_failed()
                ),
                errors={
                    "runtime": str(exc)
                },
            )

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        *,
        initialize: bool = True,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Start the runtime.

        By default, initialization is performed first when needed.
        """

        if self._running:
            return LifecycleResult(
                operation="start",
                status=(
                    self._lifecycle_status_success()
                ),
                skipped=list(
                    self.lifecycle.subsystem_names
                ),
            )

        if not self._initialized:

            if not initialize:
                raise RuntimeManagerError(
                    (
                        "Runtime has not been "
                        "initialized."
                    )
                )

            self.initialize(
                raise_on_error=raise_on_error
            )

        self._status = (
            ManagerStatus.RUNNING
        )

        try:

            result = self.lifecycle.start(
                raise_on_error=raise_on_error
            )

            if result.failed_operation:

                self._running = False

                self._status = (
                    ManagerStatus.ERROR
                )

                self._last_error = (
                    "Runtime start failed."
                )

            else:

                self._running = True

                self._paused = False

                self._status = (
                    ManagerStatus.RUNNING
                )

            return result

        except Exception as exc:

            self._running = False

            self._status = (
                ManagerStatus.ERROR
            )

            self._last_error = str(
                exc
            )

            if raise_on_error:
                raise

            return LifecycleResult(
                operation="start",
                status=(
                    self._lifecycle_status_failed()
                ),
                errors={
                    "runtime": str(exc)
                },
            )

    # ============================================================
    # PAUSE
    # ============================================================

    def pause(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Pause the runtime.
        """

        if not self._running:
            raise RuntimeManagerError(
                "Runtime is not running."
            )

        try:

            result = self.lifecycle.pause(
                raise_on_error=raise_on_error
            )

            if result.failed_operation:

                self._status = (
                    ManagerStatus.ERROR
                )

                self._last_error = (
                    "Runtime pause failed."
                )

            else:

                self._running = False

                self._paused = True

                self._status = (
                    ManagerStatus.PAUSED
                )

            return result

        except Exception as exc:

            self._status = (
                ManagerStatus.ERROR
            )

            self._last_error = str(
                exc
            )

            if raise_on_error:
                raise

            return LifecycleResult(
                operation="pause",
                status=(
                    self._lifecycle_status_failed()
                ),
                errors={
                    "runtime": str(exc)
                },
            )

    # ============================================================
    # RESUME
    # ============================================================

    def resume(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Resume a paused runtime.
        """

        if not self._paused:
            raise RuntimeManagerError(
                "Runtime is not paused."
            )

        try:

            result = self.lifecycle.resume(
                raise_on_error=raise_on_error
            )

            if result.failed_operation:

                self._status = (
                    ManagerStatus.ERROR
                )

                self._last_error = (
                    "Runtime resume failed."
                )

            else:

                self._running = True

                self._paused = False

                self._status = (
                    ManagerStatus.RUNNING
                )

            return result

        except Exception as exc:

            self._status = (
                ManagerStatus.ERROR
            )

            self._last_error = str(
                exc
            )

            if raise_on_error:
                raise

            return LifecycleResult(
                operation="resume",
                status=(
                    self._lifecycle_status_failed()
                ),
                errors={
                    "runtime": str(exc)
                },
            )

    # ============================================================
    # PROCESS ONE TURN
    # ============================================================

    def process(
        self,
        input_data: Any = None,
        *,
        turn_id: str | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
        auto_start: bool = False,
        raise_on_error: bool = True,
    ) -> PipelineResult:
        """
        Process one unit of input through the runtime pipeline.

        The runtime must be running unless auto_start=True.
        """

        if not self._running:

            if auto_start:

                self.start(
                    raise_on_error=raise_on_error
                )

            else:
                raise RuntimeManagerError(
                    (
                        "Runtime is not running. "
                        "Call start() first or "
                        "use auto_start=True."
                    )
                )

        combined_metadata = dict(
            self._metadata
        )

        if metadata is not None:
            combined_metadata.update(
                metadata
            )

        try:

            result = self.pipeline.execute(
                input_data,
                turn_id=turn_id,
                metadata=combined_metadata,
                raise_on_error=raise_on_error,
            )

            if result.failed:

                self._last_error = (
                    result.error
                )

            return result

        except Exception as exc:

            self._last_error = str(
                exc
            )

            self._status = (
                ManagerStatus.ERROR
            )

            raise

    # ============================================================
    # STOP
    # ============================================================

    def stop(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Stop the runtime.
        """

        if (
            not self._running
            and not self._paused
        ):
            return LifecycleResult(
                operation="stop",
                status=(
                    self._lifecycle_status_skipped()
                ),
                skipped=list(
                    self.lifecycle.subsystem_names
                ),
            )

        try:

            result = self.lifecycle.stop(
                raise_on_error=raise_on_error
            )

            if result.failed_operation:

                self._status = (
                    ManagerStatus.ERROR
                )

                self._last_error = (
                    "Runtime stop failed."
                )

            else:

                self._running = False

                self._paused = False

                self._status = (
                    ManagerStatus.STOPPED
                )

            return result

        except Exception as exc:

            self._status = (
                ManagerStatus.ERROR
            )

            self._last_error = str(
                exc
            )

            if raise_on_error:
                raise

            return LifecycleResult(
                operation="stop",
                status=(
                    self._lifecycle_status_failed()
                ),
                errors={
                    "runtime": str(exc)
                },
            )

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(
        self,
        *,
        raise_on_error: bool = True,
    ) -> LifecycleResult:
        """
        Shut down the runtime and release subsystem resources.
        """

        try:

            result = self.lifecycle.shutdown(
                raise_on_error=raise_on_error
            )

            if result.failed_operation:

                self._status = (
                    ManagerStatus.ERROR
                )

                self._last_error = (
                    "Runtime shutdown failed."
                )

            else:

                self._running = False

                self._paused = False

                self._initialized = False

                self._status = (
                    ManagerStatus.STOPPED
                )

            return result

        except Exception as exc:

            self._status = (
                ManagerStatus.ERROR
            )

            self._last_error = str(
                exc
            )

            if raise_on_error:
                raise

            return LifecycleResult(
                operation="shutdown",
                status=(
                    self._lifecycle_status_failed()
                ),
                errors={
                    "runtime": str(exc)
                },
            )

    # ============================================================
    # HEALTH
    # ============================================================

    def health(
        self,
    ) -> dict[str, Any]:
        """
        Return runtime and subsystem health information.
        """

        return {
            "runtime": {
                "status": self._status.value,
                "initialized": self._initialized,
                "running": self._running,
                "paused": self._paused,
                "last_error": self._last_error,
            },
            "subsystems": self.lifecycle.health(),
            "pipeline": {
                "name": self.pipeline.name,
                "stages": list(
                    self.pipeline.stage_names
                ),
                "running": self.pipeline.is_running,
                "validation_errors": (
                    self.pipeline.validate()
                ),
            },
        }

    # ============================================================
    # SNAPSHOT
    # ============================================================

    def snapshot(
        self,
    ) -> RuntimeSnapshot:
        """
        Return a compact runtime snapshot.
        """

        turn_count = getattr(
            self.state,
            "turn_count",
            0,
        )

        return RuntimeSnapshot(
            status=self._status,
            initialized=self._initialized,
            running=self._running,
            paused=self._paused,
            subsystem_names=(
                self.lifecycle.subsystem_names
            ),
            pipeline_stages=(
                self.pipeline.stage_names
            ),
            turn_count=turn_count,
            last_error=self._last_error,
            metadata=dict(
                self._metadata
            ),
        )

    # ============================================================
    # PROPERTIES
    # ============================================================

    @property
    def status(
        self,
    ) -> ManagerStatus:
        return self._status

    @property
    def initialized(
        self,
    ) -> bool:
        return self._initialized

    @property
    def running(
        self,
    ) -> bool:
        return self._running

    @property
    def paused(
        self,
    ) -> bool:
        return self._paused

    @property
    def last_error(
        self,
    ) -> str | None:
        return self._last_error

    # ============================================================
    # INTERNAL STATUS HELPERS
    # ============================================================

    @staticmethod
    def _lifecycle_status_success():
        """
        Avoid coupling manager callers to a specific enum import.
        """

        from .lifecycle import LifecycleStatus

        return LifecycleStatus.SUCCESS

    @staticmethod
    def _lifecycle_status_failed():

        from .lifecycle import LifecycleStatus

        return LifecycleStatus.FAILED

    @staticmethod
    def _lifecycle_status_skipped():

        from .lifecycle import LifecycleStatus

        return LifecycleStatus.SKIPPED


# ================================================================
# FACTORY
# ================================================================


def create_runtime_manager(
    *,
    runtime_state: RuntimeState | None = None,
    lifecycle: RuntimeLifecycle | None = None,
    pipeline: Pipeline | None = None,
    subsystems: Iterable[
        SubsystemLifecycleAdapter
    ]
    | None = None,
    stages: Sequence[
        PipelineStage
    ]
    | None = None,
    metadata: Mapping[
        str,
        Any,
    ]
    | None = None,
) -> RuntimeManager:
    """
    Construct a runtime manager from explicitly supplied
    components.

    Nothing is automatically discovered, enabled, or connected.
    """

    manager = RuntimeManager(
        runtime_state=runtime_state,
        lifecycle=lifecycle,
        pipeline=pipeline,
        metadata=metadata,
    )

    if subsystems is not None:
        manager.register_subsystems(
            subsystems
        )

    if stages is not None:
        for stage in stages:
            manager.add_stage(
                stage
            )

    return manager