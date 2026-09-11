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
    "sanitize_mcp_result",
    "sanitize_mcp_task_args",
    "server_config_from_environment",
    "default_permission_path",
    "capabilities_from_environment",
    "preview_capability_task",
]

from .action_windows import ActionSpec, ActionWindow, ActionSelection, ActionWindowRegistry
