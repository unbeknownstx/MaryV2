"""Distributed-runtime primitives for MaryV2."""
from .capabilities import CapabilityDescriptor, capabilities_from_environment
from .nodes import NodeDescriptor, NodeRegistry
from .tasks import CapabilityTaskPlan, preview_capability_task

__all__ = [
    "CapabilityDescriptor",
    "NodeDescriptor",
    "NodeRegistry",
    "CapabilityTaskPlan",
    "capabilities_from_environment",
    "preview_capability_task",
]
