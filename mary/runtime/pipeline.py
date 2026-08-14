"""
MaryV2 - Runtime Pipeline

Defines Mary's turn-processing pipeline.

The pipeline is responsible for coordinating an individual unit of
interaction through explicitly supplied processing stages.

It does NOT:

    - automatically discover subsystems
    - access the internet
    - create or enable tools
    - select an LLM provider
    - access audio hardware
    - directly modify memory
    - contain Mary's personality
    - contain Mary's reasoning logic

Those responsibilities belong to their respective subsystems.

The pipeline only coordinates them.

Architecture:

    Input
      |
      v
    Perception
      |
      v
    Understanding
      |
      v
    Cognition
      |
      v
    Memory / Knowledge
      |
      v
    Decision
      |
      v
    Response
      |
      v
    Voice / Output
"""


from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, Mapping, Sequence

from .state import RuntimeState


# ================================================================
# PIPELINE STATUS
# ================================================================


class PipelineStatus(str, Enum):
    """
    State of a pipeline execution.
    """

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ================================================================
# PIPELINE ERRORS
# ================================================================


class PipelineError(RuntimeError):
    """
    Base pipeline exception.
    """


class PipelineStageError(PipelineError):
    """
    Raised when a pipeline stage fails.
    """


class PipelineCancelledError(PipelineError):
    """
    Raised when pipeline execution is cancelled.
    """


class PipelineConfigurationError(PipelineError):
    """
    Raised when the pipeline is configured incorrectly.
    """


# ================================================================
# PIPELINE CONTEXT
# ================================================================


@dataclass
class PipelineContext:
    """
    Context shared between pipeline stages during one turn.

    Stages communicate through this context rather than directly
    reaching into unrelated subsystems.
    """

    runtime_state: RuntimeState

    turn_id: str

    input_data: Any = None

    output_data: Any = None

    values: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    cancelled: bool = False

    started_at: float = field(
        default_factory=time
    )

    completed_at: float | None = None

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a pipeline value.
        """

        self.values[key] = value

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a pipeline value.
        """

        return self.values.get(
            key,
            default,
        )

    def require(
        self,
        key: str,
    ) -> Any:
        """
        Retrieve a required pipeline value.
        """

        if key not in self.values:
            raise PipelineConfigurationError(
                f"Required pipeline value is missing: {key}"
            )

        return self.values[key]

    def cancel(self) -> None:
        """
        Request cancellation of the current pipeline execution.
        """

        self.cancelled = True

    @property
    def elapsed(self) -> float | None:
        """
        Return elapsed processing time.
        """

        end = (
            self.completed_at
            if self.completed_at is not None
            else time()
        )

        return max(
            0.0,
            end - self.started_at,
        )


# ================================================================
# PIPELINE STAGE RESULT


@dataclass
class StageResult:
    """
    Result returned by an individual pipeline stage.
    """

    success: bool = True

    output: Any = None

    values: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    error: str | None = None

    skipped: bool = False

    stop_pipeline: bool = False

    def apply_to(
        self,
        context: PipelineContext,
    ) -> None:
        """
        Apply this stage result to the pipeline context.
        """

        if self.output is not None:
            context.output_data = self.output

        context.values.update(
            self.values
        )

        context.metadata.update(
            self.metadata
        )


# ================================================================
# PIPELINE STAGE
# ================================================================


class PipelineStage:
    """
    General runtime pipeline stage.

    A stage can be created directly with a handler.
    """

    def __init__(
        self,
        name: str = "stage",
        handler: Callable[
            [PipelineContext],
            Any,
        ] | None = None,
        *,
        required: bool = True,
        enabled: bool = True,
    ) -> None:

        if handler is None:
            raise PipelineConfigurationError(
                f"PipelineStage '{name}' requires a handler."
            )

        self.name = name
        self.handler = handler
        self.required = required
        self.enabled = enabled

    def process(
        self,
        context: PipelineContext,
    ) -> StageResult | Any:
        """
        Execute the stage handler.
        """

        return self.handler(context)

    def before(
        self,
        context: PipelineContext,
    ) -> None:
        """
        Optional hook executed before process().
        """

    def after(
        self,
        context: PipelineContext,
        result: StageResult,
    ) -> None:
        """
        Optional hook executed after process().
        """

    def on_error(
        self,
        context: PipelineContext,
        error: Exception,
    ) -> None:
        """
        Optional error hook.
        """


# ================================================================
# CALLBACK STAGE
# ================================================================


class CallbackStage(PipelineStage):
    """
    Lightweight stage adapter for existing functions.

    Uses an explicit constructor instead of a dataclass because
    PipelineStage already defines default-valued fields.
    """

    def __init__(
        self,
        name: str,
        callback: Callable[
            [PipelineContext],
            Any,
        ],
        *,
        required: bool = True,
        enabled: bool = True,
    ) -> None:

        super().__init__(
            name=name,
            required=required,
            enabled=enabled,
        )

        self.callback = callback

    def process(
        self,
        context: PipelineContext,
    ) -> StageResult | Any:

        return self.callback(
            context
        )


# ================================================================
# STAGE EXECUTION RECORD
# ================================================================


@dataclass
class StageExecution:
    """
    Records what happened during one stage execution.
    """

    name: str

    status: str = "pending"

    started_at: float | None = None

    completed_at: float | None = None

    output: Any = None

    error: str | None = None

    skipped: bool = False

    @property
    def elapsed(self) -> float | None:
        if (
            self.started_at is None
            or self.completed_at is None
        ):
            return None

        return max(
            0.0,
            self.completed_at
            - self.started_at,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed": self.elapsed,
            "output": self.output,
            "error": self.error,
            "skipped": self.skipped,
        }


# ================================================================
# PIPELINE RESULT
# ================================================================


@dataclass
class PipelineResult:
    """
    Complete result of one pipeline execution.
    """

    status: PipelineStatus

    turn_id: str

    input_data: Any = None

    output_data: Any = None

    stage_results: list[
        StageExecution
    ] = field(
        default_factory=list
    )

    error: str | None = None

    started_at: float | None = None

    completed_at: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def successful(self) -> bool:
        return (
            self.status
            == PipelineStatus.COMPLETED
        )

    @property
    def success(self) -> bool:
        """
        Compatibility alias for successful.
        """

        return self.successful

    @property
    def output(self) -> Any:
        """
        Compatibility alias for output_data.
        """

        return self.output_data

    @property
    def failed(self) -> bool:
        return (
            self.status
            == PipelineStatus.FAILED
        )

    @property
    def cancelled(self) -> bool:
        return (
            self.status
            == PipelineStatus.CANCELLED
        )

    @property
    def elapsed(self) -> float | None:

        if (
            self.started_at is None
            or self.completed_at is None
        ):
            return None

        return max(
            0.0,
            self.completed_at
            - self.started_at,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "status": self.status.value,
            "turn_id": self.turn_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "stage_results": [
                stage.to_dict()
                for stage
                in self.stage_results
            ],
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed": self.elapsed,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# PIPELINE
# ================================================================


class Pipeline:
    """
    Executes explicitly registered processing stages in order.

    The pipeline has no automatic stage discovery.
    """

    def __init__(
        self,
        runtime_state: RuntimeState,
        *,
        stages: Sequence[
            PipelineStage
        ]
        | None = None,
        name: str = "main",
    ) -> None:

        self.runtime_state = runtime_state

        self.name = str(
            name
        ).strip()

        if not self.name:
            raise ValueError(
                "Pipeline name cannot be empty."
            )

        self._stages: list[
            PipelineStage
        ] = []

        self._running = False

        self._cancel_requested = False

        if stages is not None:
            for stage in stages:
                self.add_stage(
                    stage
                )

    # ============================================================
    # STAGE MANAGEMENT
    # ============================================================

    def add_stage(
        self,
        stage: PipelineStage,
    ) -> None:
        """
        Add a stage to the end of the pipeline.
        """

        if not isinstance(
            stage,
            PipelineStage,
        ):
            raise TypeError(
                "stage must implement PipelineStage."
            )

        if any(
            existing.name == stage.name
            for existing in self._stages
        ):
            raise PipelineConfigurationError(
                f"Pipeline stage already exists: {stage.name}"
            )

        self._stages.append(
            stage
        )

    def insert_stage(
        self,
        index: int,
        stage: PipelineStage,
    ) -> None:
        """
        Insert a stage at a specific position.
        """

        if not isinstance(
            stage,
            PipelineStage,
        ):
            raise TypeError(
                "stage must implement PipelineStage."
            )

        if any(
            existing.name == stage.name
            for existing in self._stages
        ):
            raise PipelineConfigurationError(
                f"Pipeline stage already exists: {stage.name}"
            )

        self._stages.insert(
            index,
            stage,
        )

    def remove_stage(
        self,
        name: str,
    ) -> bool:
        """
        Remove a stage by name.
        """

        for index, stage in enumerate(
            self._stages
        ):
            if stage.name == name:
                del self._stages[index]

                return True

        return False

    def get_stage(
        self,
        name: str,
    ) -> PipelineStage | None:
        """
        Retrieve a stage by name.
        """

        for stage in self._stages:
            if stage.name == name:
                return stage

        return None

    @property
    def stages(
        self,
    ) -> tuple[
        PipelineStage,
        ...,
    ]:
        """
        Return registered stages.
        """

        return tuple(
            self._stages
        )

    @property
    def stage_names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            stage.name
            for stage in self._stages
        )

    # ============================================================
    # EXECUTE
    # ============================================================

    def run(
        self,
        input_data: Any = None,
        *,
        turn_id: str | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> PipelineResult:
        """
        Execute the pipeline.

        This is the primary convenience interface for callers.
        It delegates to the existing execute() implementation.
        """

        return self.execute(
            input_data=input_data,
            turn_id=turn_id,
            metadata=metadata,
        )

    def execute(
        self,
        input_data: Any = None,
        *,
        turn_id: str | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
        raise_on_error: bool = True,
    ) -> PipelineResult:
        """
        Execute one pipeline turn.

        Only explicitly registered and enabled stages execute.
        """

        if self._running:
            raise PipelineError(
                "Pipeline is already running."
            )

        if turn_id is None:
            turn_id = (
                f"turn-{int(time() * 1000000)}"
            )

        context = PipelineContext(
            runtime_state=self.runtime_state,
            turn_id=turn_id,
            input_data=input_data,
            metadata=dict(
                metadata
                if metadata is not None
                else {}
            ),
        )

        result = PipelineResult(
            status=PipelineStatus.RUNNING,
            turn_id=turn_id,
            input_data=input_data,
            started_at=time(),
        )

        self._running = True

        self._cancel_requested = False

        try:
            for stage in self._stages:

                if self._cancel_requested:
                    context.cancel()

                if context.cancelled:
                    result.status = (
                        PipelineStatus.CANCELLED
                    )

                    break

                execution = (
                    StageExecution(
                        name=stage.name,
                        started_at=time(),
                    )
                )

                result.stage_results.append(
                    execution
                )

                if not stage.enabled:
                    execution.status = (
                        "skipped"
                    )

                    execution.skipped = True

                    execution.completed_at = time()

                    continue

                try:
                    stage.before(
                        context
                    )

                    raw_result = (
                        stage.process(
                            context
                        )
                    )

                    stage_result = (
                        self._normalize_result(
                            raw_result
                        )
                    )

                    stage_result.apply_to(
                        context
                    )

                    stage.after(
                        context,
                        stage_result,
                    )

                    execution.output = (
                        stage_result.output
                    )

                    execution.completed_at = time()

                    if stage_result.skipped:
                        execution.status = (
                            "skipped"
                        )

                        execution.skipped = True

                    elif not stage_result.success:
                        execution.status = (
                            "failed"
                        )

                        execution.error = (
                            stage_result.error
                            or "Stage failed."
                        )

                        if stage.required:
                            raise PipelineStageError(
                                (
                                    f"Required stage "
                                    f"'{stage.name}' "
                                    f"failed: "
                                    f"{execution.error}"
                                )
                            )

                    else:
                        execution.status = (
                            "completed"
                        )

                    if stage_result.stop_pipeline:
                        break

                except Exception as exc:

                    execution.status = (
                        "failed"
                    )

                    execution.error = str(
                        exc
                    )

                    execution.completed_at = time()

                    stage.on_error(
                        context,
                        exc,
                    )

                    if stage.required:

                        if raise_on_error:
                            raise PipelineStageError(
                                (
                                    f"Pipeline stage "
                                    f"'{stage.name}' "
                                    f"failed: {exc}"
                                )
                            ) from exc

                        result.error = str(
                            exc
                        )

                        result.status = (
                            PipelineStatus.FAILED
                        )

                        break

            else:
                result.status = (
                    PipelineStatus.COMPLETED
                )

            result.output_data = (
                context.output_data
            )

            result.metadata.update(
                context.metadata
            )

            result.metadata[
                "pipeline_values"
            ] = dict(
                context.values
            )

            result.completed_at = time()

            if (
                result.status
                == PipelineStatus.RUNNING
            ):
                result.status = (
                    PipelineStatus.COMPLETED
                )

            self.runtime_state.increment_turn()

            return result

        except PipelineStageError as exc:

            result.status = (
                PipelineStatus.FAILED
            )

            result.error = str(
                exc
            )

            result.completed_at = time()

            if raise_on_error:
                raise

            return result

        except Exception as exc:

            result.status = (
                PipelineStatus.FAILED
            )

            result.error = str(
                exc
            )

            result.completed_at = time()

            if raise_on_error:
                raise PipelineError(
                    (
                        f"Pipeline '{self.name}' "
                        f"failed: {exc}"
                    )
                ) from exc

            return result

        finally:
            self._running = False

            self._cancel_requested = False

    # ============================================================
    # CANCELLATION
    # ============================================================

    def cancel(self) -> None:
        """
        Request cancellation of the active pipeline.
        """

        self._cancel_requested = True

    @property
    def is_running(
        self,
    ) -> bool:
        return self._running

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate(
        self,
    ) -> list[str]:
        """
        Validate the current pipeline configuration.

        Returns a list of configuration errors.
        """

        errors: list[str] = []

        names: set[str] = set()

        for stage in self._stages:

            if not stage.name.strip():
                errors.append(
                    "Pipeline contains a stage with an empty name."
                )

            if stage.name in names:
                errors.append(
                    (
                        "Duplicate pipeline stage: "
                        f"{stage.name}"
                    )
                )

            names.add(
                stage.name
            )

        return errors

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    @staticmethod
    def _normalize_result(
        value: StageResult | Any,
    ) -> StageResult:
        """
        Normalize arbitrary stage return values.
        """

        if isinstance(
            value,
            StageResult,
        ):
            return value

        return StageResult(
            success=True,
            output=value,
        )


# ================================================================
# PIPELINE BUILDER
# ================================================================


class PipelineBuilder:
    """
    Fluent builder for explicit pipeline construction.
    """

    def __init__(
        self,
        runtime_state: RuntimeState,
        *,
        name: str = "main",
    ) -> None:

        self._pipeline = Pipeline(
            runtime_state,
            name=name,
        )

    def add(
        self,
        stage: PipelineStage,
    ) -> "PipelineBuilder":
        self._pipeline.add_stage(
            stage
        )

        return self

    def add_callback(
        self,
        name: str,
        callback: Callable[
            [PipelineContext],
            Any,
        ],
        *,
        required: bool = True,
        enabled: bool = True,
    ) -> "PipelineBuilder":

        self._pipeline.add_stage(
            CallbackStage(
                name=name,
                callback=callback,
                required=required,
                enabled=enabled,
            )
        )

        return self

    def build(
        self,
    ) -> Pipeline:
        """
        Validate and return the pipeline.
        """

        errors = (
            self._pipeline.validate()
        )

        if errors:
            raise PipelineConfigurationError(
                "; ".join(errors)
            )

        return self._pipeline


# ================================================================
# SIMPLE PIPELINE STAGES FOR TESTING
# ================================================================


class PassThroughStage(
    PipelineStage
):
    """
    Simple stage that passes input through unchanged.

    Useful for testing the pipeline without connecting actual
    Mary subsystems.
    """

    def __init__(
        self,
        name: str,
    ) -> None:

        self.name = name

    def process(
        self,
        context: PipelineContext,
    ) -> StageResult:

        return StageResult(
            success=True,
            output=context.input_data,
        )


class TransformStage(
    PipelineStage
):
    """
    Test/helper stage that transforms input using a supplied
    function.
    """

    def __init__(
        self,
        name: str,
        transform: Callable[
            [Any],
            Any,
        ],
    ) -> None:

        self.name = name

        self.transform = transform

    def process(
        self,
        context: PipelineContext,
    ) -> StageResult:

        output = self.transform(
            context.input_data
        )

        return StageResult(
            success=True,
            output=output,
        )


# ================================================================
# FACTORY
# ================================================================


def create_pipeline(
    runtime_state: RuntimeState,
    stages: Sequence[
        PipelineStage
    ],
    *,
    name: str = "main",
) -> Pipeline:
    """
    Create and validate an explicitly configured pipeline.
    """

    pipeline = Pipeline(
        runtime_state,
        name=name,
        stages=stages,
    )

    errors = pipeline.validate()

    if errors:
        raise PipelineConfigurationError(
            "; ".join(errors)
        )

    return pipeline