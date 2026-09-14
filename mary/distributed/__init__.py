"""Distributed-runtime primitives for MaryV2."""
from .capabilities import CapabilityDescriptor, capabilities_from_environment
from .nodes import NodeDescriptor, NodeRegistry
from .mcp_fabric import (
    MCP_CAPABILITIES,
    MCP_SERVER_CAPABILITIES,
    MCPFabric,
    MCPServerConfig,
    mcp_dependency_available,
    normalize_mcp_tool_name,
    sanitize_mcp_error,
    sanitize_mcp_result,
    sanitize_mcp_task_args,
    server_config_from_environment,
)
from .permissions import DeviceExecutionPermissions, default_permission_path
from .tasks import (
    CapabilityTaskPlan,
    DeviceCapabilityTask,
    DeviceTaskBroker,
    preview_capability_task,
)
from .compute_fabric import (
    BenchmarkBook,
    BenchmarkSample,
    HomeComputeScheduler,
    NodeLoad,
    WorkloadRequest,
    WORKLOAD_PROFILES,
    workload,
)
from .benchmarking import (
    PROFILE_VERSION,
    RELIABILITY_REVISION,
    STANDARD_LLM_CASES,
    apply_benchmark_profile,
    benchmark_local_llm,
    build_profile,
    cpu_reference_benchmark,
    host_fingerprint,
    load_profile,
    node_id_from_environment,
    save_profile,
    useful_throughput,
)
from .execution_reliability import (
    ExecutionBudget,
    ExecutionEvidence,
    ProgressGuard,
    ReliabilityLedger,
    ReliabilityVerdict,
    compact_error_class,
    derive_side_effect_key,
    should_retry,
    stable_args_fingerprint,
    transient_error,
)
from .model_capability_evidence import (
    CapabilityProbeResult,
    ModelCapabilityEvidence,
    build_capability_evidence,
    run_boolean_probe,
)
from .resource_broker import (
    ResourceHandoffPlan,
    ResourceSnapshot,
    WorkloadFootprint,
    plan_resource_handoff,
)
from .resource_probe import (
    GPUObservation,
    LiveResourceObservation,
    observe_live_resources,
    resource_snapshot,
)
from .specialist_catalog import CATALOG as SPECIALIST_CATALOG, SpecialistBackend, backend as specialist_backend, specialist_status

__all__ = [
    "CapabilityDescriptor",
    "NodeDescriptor",
    "NodeRegistry",
    "CapabilityTaskPlan",
    "DeviceCapabilityTask",
    "DeviceTaskBroker",
    "DeviceExecutionPermissions",
    "MCP_CAPABILITIES",
    "MCP_SERVER_CAPABILITIES",
    "MCPFabric",
    "MCPServerConfig",
    "mcp_dependency_available",
    "normalize_mcp_tool_name",
    "sanitize_mcp_error",
    "sanitize_mcp_result",
    "sanitize_mcp_task_args",
    "server_config_from_environment",
    "default_permission_path",
    "capabilities_from_environment",
    "preview_capability_task",
    "BenchmarkBook",
    "BenchmarkSample",
    "HomeComputeScheduler",
    "NodeLoad",
    "WorkloadRequest",
    "WORKLOAD_PROFILES",
    "workload",
    "PROFILE_VERSION",
    "RELIABILITY_REVISION",
    "STANDARD_LLM_CASES",
    "apply_benchmark_profile",
    "benchmark_local_llm",
    "build_profile",
    "cpu_reference_benchmark",
    "host_fingerprint",
    "load_profile",
    "node_id_from_environment",
    "save_profile",
    "useful_throughput",
    "ExecutionBudget",
    "ExecutionEvidence",
    "ProgressGuard",
    "ReliabilityLedger",
    "ReliabilityVerdict",
    "compact_error_class",
    "derive_side_effect_key",
    "should_retry",
    "stable_args_fingerprint",
    "transient_error",
    "CapabilityProbeResult",
    "ModelCapabilityEvidence",
    "build_capability_evidence",
    "run_boolean_probe",
    "ResourceHandoffPlan",
    "ResourceSnapshot",
    "WorkloadFootprint",
    "plan_resource_handoff",
    "GPUObservation",
    "LiveResourceObservation",
    "observe_live_resources",
    "resource_snapshot",
    "SPECIALIST_CATALOG",
    "SpecialistBackend",
    "specialist_backend",
    "specialist_status",
]

from .action_windows import ActionSpec, ActionWindow, ActionSelection, ActionWindowRegistry

from .invocations import CapabilityInvocation, CapabilityInvocationLedger
from .simulator import CapabilitySimulator, SimulatedCapabilityResult

__all__ += [
    "CapabilityInvocation",
    "CapabilityInvocationLedger",
    "CapabilitySimulator",
    "SimulatedCapabilityResult",
]
