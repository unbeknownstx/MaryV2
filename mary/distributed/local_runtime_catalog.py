"""Named local-inference runtimes for Mary's heterogeneous compute fabric.

The catalog describes optional runtimes without importing or contacting them at
Core startup.  It deliberately reuses Mary's generic OpenAI-compatible provider
for server-style runtimes instead of creating duplicate model/provider logic.

A runtime descriptor is capability metadata only: it does not authorize use,
prove that a server is listening, or change Mary Core/model routing policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
import os
from typing import Any


@dataclass(frozen=True)
class LocalRuntimeDescriptor:
    name: str
    engine: str
    protocol: str
    default_base_url: str = ""
    base_url_env: str = ""
    model_env: str = ""
    ready_env: str = ""
    module_hint: str = ""
    apple_silicon_native: bool = False
    supports_embeddings: bool | None = None
    supports_model_lifecycle: bool = False
    notes: str = ""

    def configured(self) -> bool:
        if self.ready_env and _flag(self.ready_env):
            return True
        if self.base_url_env and os.getenv(self.base_url_env, "").strip():
            return True
        if self.module_hint and _module(self.module_hint):
            return True
        return False

    def base_url(self) -> str:
        configured = os.getenv(self.base_url_env, "").strip() if self.base_url_env else ""
        return configured or self.default_base_url

    def model(self) -> str:
        return os.getenv(self.model_env, "").strip() if self.model_env else ""

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update({
            "configured": self.configured(),
            "base_url": self.base_url(),
            "model": self.model(),
            "local": True,
            "private": True,
            "cost": "local",
            "startup_dependency": False,
        })
        # Diagnostics should expose env names, never key values.
        return payload


def _module(name: str) -> bool:
    try:
        return bool(name) and find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on", "enabled"}


LOCAL_RUNTIMES: dict[str, LocalRuntimeDescriptor] = {
    "ollama": LocalRuntimeDescriptor(
        name="ollama",
        engine="ollama",
        protocol="ollama_api",
        default_base_url="http://127.0.0.1:11434",
        base_url_env="MARY_OLLAMA_BASE_URL",
        model_env="MARY_OLLAMA_MODEL",
        ready_env="MARY_OLLAMA_ENABLED",
        supports_embeddings=True,
        supports_model_lifecycle=True,
        notes="Mary's existing simple local model runtime.",
    ),
    "llama_cpp": LocalRuntimeDescriptor(
        name="llama_cpp",
        engine="llama.cpp",
        protocol="native_or_openai_compatible",
        base_url_env="MARY_LLAMA_CPP_BASE_URL",
        model_env="MARY_LLAMA_CPP_MODEL",
        ready_env="MARY_LLAMA_CPP_READY",
        module_hint="llama_cpp",
        supports_embeddings=True,
        supports_model_lifecycle=False,
        notes="Lower-level GGUF runtime; compatible builds may expose native MTP/speculative decoding.",
    ),
    "lm_studio": LocalRuntimeDescriptor(
        name="lm_studio",
        engine="llama.cpp/runtime-managed",
        protocol="openai_compatible",
        default_base_url="http://127.0.0.1:1234/v1",
        base_url_env="MARY_LM_STUDIO_BASE_URL",
        model_env="MARY_LM_STUDIO_MODEL",
        ready_env="MARY_LM_STUDIO_READY",
        supports_embeddings=True,
        supports_model_lifecycle=True,
        notes="Optional LM Studio server. Mary reuses her generic OpenAI-compatible transport.",
    ),
    "jan": LocalRuntimeDescriptor(
        name="jan",
        engine="llama.cpp/MLX",
        protocol="openai_compatible",
        default_base_url="http://127.0.0.1:1337/v1",
        base_url_env="MARY_JAN_BASE_URL",
        model_env="MARY_JAN_MODEL",
        ready_env="MARY_JAN_READY",
        apple_silicon_native=True,
        supports_embeddings=None,
        supports_model_lifecycle=True,
        notes="Optional Jan local server/router; current llama.cpp path may expose GGUF MTP.",
    ),
    "mlx": LocalRuntimeDescriptor(
        name="mlx",
        engine="MLX",
        protocol="native_or_server_adapter",
        model_env="MARY_MLX_MODEL",
        ready_env="MARY_MLX_READY",
        module_hint="mlx_lm",
        apple_silicon_native=True,
        supports_embeddings=None,
        supports_model_lifecycle=False,
        notes="Apple-Silicon-native inference candidate; benchmark before promotion.",
    ),
}


def runtime_descriptor(name: str) -> LocalRuntimeDescriptor | None:
    return LOCAL_RUNTIMES.get(str(name or "").strip().lower())


def local_runtime_catalog() -> list[dict[str, Any]]:
    return [LOCAL_RUNTIMES[name].public_dict() for name in LOCAL_RUNTIMES]


def openai_compatible_runtime_provider(name: str):
    """Build Mary's existing transport for a configured local compatible server.

    Import is lazy to keep local-runtime discovery free of provider dependencies.
    The caller still decides whether this runtime is eligible for a task.
    """

    descriptor = runtime_descriptor(name)
    if descriptor is None or descriptor.protocol != "openai_compatible":
        raise ValueError(f"local runtime is not OpenAI-compatible: {name}")
    from mary.llm.providers.openai_compatible import OpenAICompatibleProvider

    return OpenAICompatibleProvider(
        provider_name=descriptor.name,
        base_url=descriptor.base_url(),
        model=descriptor.model(),
    )
