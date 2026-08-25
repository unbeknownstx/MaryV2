"""Distributed-runtime primitives for MaryV2."""
from .capabilities import CapabilityDescriptor, capabilities_from_environment
from .nodes import NodeDescriptor, NodeRegistry

__all__ = ["CapabilityDescriptor", "NodeDescriptor", "NodeRegistry", "capabilities_from_environment"]
