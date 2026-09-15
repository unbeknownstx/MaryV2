"""Provider-neutral creative capability descriptors for MaryV2.

Creative apps/runtimes are replaceable capability nodes, not Mary Core and not
startup dependencies.  This module only describes explicitly configured local
creative surfaces. Actual execution must still travel through Mary's bounded
device-task/tool permission channel.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any


_ALLOWED_OPERATIONS = frozenset({
    "text_to_image",
    "image_to_image",
    "inpaint",
    "upscale",
    "text_to_video",
    "image_to_video",
})


@dataclass(frozen=True)
class CreativeRuntimeDescriptor:
    name: str
    platform: str
    operations: frozenset[str]
    local: bool = True
    private: bool = True
    cost: str = "local"
    transport: str = "configured_adapter"
    endpoint_env: str = ""
    ready_env: str = ""
    notes: str = ""

    def configured(self) -> bool:
        if self.ready_env and _flag(self.ready_env):
            return True
        if self.endpoint_env and os.getenv(self.endpoint_env, "").strip():
            return True
        return False

    def endpoint_configured(self) -> bool:
        return bool(self.endpoint_env and os.getenv(self.endpoint_env, "").strip())

    def supports(self, operation: str) -> bool:
        return str(operation or "").strip().lower() in self.operations

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["operations"] = sorted(self.operations)
        data.update({
            "configured": self.configured(),
            "endpoint_configured": self.endpoint_configured(),
            "startup_dependency": False,
            "authority": "creative_execution_only",
        })
        return data


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _ops(*items: str) -> frozenset[str]:
    normalized = frozenset(str(item).strip().lower() for item in items)
    if not normalized.issubset(_ALLOWED_OPERATIONS):
        raise ValueError("unsupported creative operation")
    return normalized


CREATIVE_RUNTIMES: dict[str, CreativeRuntimeDescriptor] = {
    "draw_things": CreativeRuntimeDescriptor(
        name="draw_things",
        platform="apple",
        operations=_ops(
            "text_to_image",
            "image_to_image",
            "inpaint",
            "upscale",
            "text_to_video",
            "image_to_video",
        ),
        transport="script_or_configured_local_bridge",
        endpoint_env="MARY_DRAW_THINGS_ENDPOINT",
        ready_env="MARY_DRAW_THINGS_READY",
        notes=(
            "Apple-local creative runtime. Prefer its versioned scripting contract; "
            "any network bridge must be explicitly configured on the device."
        ),
    ),
    "local_upscaler": CreativeRuntimeDescriptor(
        name="local_upscaler",
        platform="cross_platform",
        operations=_ops("upscale"),
        transport="configured_local_tool",
        endpoint_env="MARY_LOCAL_UPSCALER_ENDPOINT",
        ready_env="MARY_LOCAL_UPSCALER_READY",
        notes="Represents Upscayl/Real-ESRGAN/WebGPU-style local enhancement workers.",
    ),
    "comfyui": CreativeRuntimeDescriptor(
        name="comfyui",
        platform="cross_platform",
        operations=_ops(
            "text_to_image",
            "image_to_image",
            "inpaint",
            "upscale",
            "text_to_video",
            "image_to_video",
        ),
        transport="configured_workflow_api",
        endpoint_env="MARY_COMFYUI_ENDPOINT",
        ready_env="MARY_COMFYUI_READY",
        notes="Workflow-oriented creative worker; never required by Core startup.",
    ),
    "client_webgpu": CreativeRuntimeDescriptor(
        name="client_webgpu",
        platform="browser",
        operations=_ops("upscale", "text_to_image"),
        transport="client_capability_channel",
        ready_env="MARY_CLIENT_WEBGPU_READY",
        notes="For explicitly advertised browser/iPad/iPhone client-side neural workloads.",
    ),
}


def creative_runtime(name: str) -> CreativeRuntimeDescriptor | None:
    return CREATIVE_RUNTIMES.get(str(name or "").strip().lower())


def creative_runtime_catalog() -> list[dict[str, Any]]:
    return [CREATIVE_RUNTIMES[name].public_dict() for name in CREATIVE_RUNTIMES]


def creative_candidates(operation: str) -> list[dict[str, Any]]:
    op = str(operation or "").strip().lower()
    if op not in _ALLOWED_OPERATIONS:
        return []
    return [
        descriptor.public_dict()
        for descriptor in CREATIVE_RUNTIMES.values()
        if descriptor.supports(op) and descriptor.configured()
    ]
