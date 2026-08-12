"""
MaryV2 - Runtime Layer

Coordinates Mary's runtime state, lifecycle, processing pipeline,
and top-level runtime management.

This package does not automatically discover, enable, or connect
external capabilities.
"""

from .state import (
    RuntimeState,
    RuntimeStatus,
    SubsystemState,
    SubsystemStatus,
)

from .lifecycle import (
    LifecycleContext,
    LifecycleError,
    LifecycleInitializationError,
    LifecyclePauseError,
    LifecycleResult,
    LifecycleShutdownError,
    LifecycleStartError,
    LifecycleStatus,
    LifecycleStopError,
    RuntimeLifecycle,
    SubsystemLifecycleAdapter,
    CallbackSubsystem,
    BasicSubsystem,
    create_runtime_lifecycle,
)

from .pipeline import (
    Pipeline,
    PipelineBuilder,
    PipelineContext,
    PipelineError,
    PipelineResult,
    PipelineStage,
    PipelineStageError,
    PipelineCancelledError,
    PipelineConfigurationError,
    StageExecution,
    StageResult,
    CallbackStage,
    PassThroughStage,
    TransformStage,
    create_pipeline,
)

from .manager import (
    ManagerStatus,
    RuntimeManager,
    RuntimeManagerError,
    RuntimeSnapshot,
    create_runtime_manager,
)


__all__ = [
    # ------------------------------------------------------------
    # State
    # ------------------------------------------------------------

    "RuntimeState",
    "RuntimeStatus",
    "SubsystemState",
    "SubsystemStatus",

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    "LifecycleContext",
    "LifecycleError",
    "LifecycleInitializationError",
    "LifecyclePauseError",
    "LifecycleResult",
    "LifecycleShutdownError",
    "LifecycleStartError",
    "LifecycleStatus",
    "LifecycleStopError",
    "RuntimeLifecycle",
    "SubsystemLifecycleAdapter",
    "CallbackSubsystem",
    "BasicSubsystem",
    "create_runtime_lifecycle",

    # ------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------

    "Pipeline",
    "PipelineBuilder",
    "PipelineContext",
    "PipelineError",
    "PipelineResult",
    "PipelineStage",
    "PipelineStageError",
    "PipelineCancelledError",
    "PipelineConfigurationError",
    "StageExecution",
    "StageResult",
    "CallbackStage",
    "PassThroughStage",
    "TransformStage",
    "create_pipeline",

    # ------------------------------------------------------------
    # Manager
    # ------------------------------------------------------------

    "ManagerStatus",
    "RuntimeManager",
    "RuntimeManagerError",
    "RuntimeSnapshot",
    "create_runtime_manager",
]