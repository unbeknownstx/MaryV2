"""Capability descriptors for MaryV2 local/remote compute nodes.

Capabilities are descriptions of what a node can do, not permission grants.
The registry is intentionally transport-agnostic so the same model can later be
used by a cloud control plane, a home PC agent, or an embedded runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from typing import Any

from .resource_profile import RuntimeResourceProfile

_CAPABILITY_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
_READINESS = {"ready", "degraded", "starting", "unavailable"}
_SECRET_KEYS = {
    "token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "cookie",
    "credential",
}

_IMPLEMENTATION_METADATA_KEYS = (
    "runtime",
    "runtime_version",
    "model",
    "configured_model",
    "model_version",
    "adapter_fingerprint",
    "artifact_fingerprint",
    "model_experiment_id",
    "model_experiment_bundle_lineage_fingerprint",
    "bundle_lineage_fingerprint",
    "backend",
    "backend_version",
    "engine",
    "engine_version",
    "tool_version",
    "schema_version",
    "implementation_version",
    "ingestion_pipeline_fingerprint",
    "pipeline_fingerprint",
    "index_pipeline_fingerprint",
    "embedding_model",
    "embedding_identity_fingerprint",
)


def _safe_metadata(values: dict[str, Any] | None) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in list(dict(values or {}).items())[:16]:
        clean_key = str(key).strip()[:80]
        lowered = clean_key.casefold()
        if not clean_key or any(secret in lowered for secret in _SECRET_KEYS):
            continue
        if isinstance(value, (bool, int, float)):
            output[clean_key] = value
        elif value is not None:
            output[clean_key] = str(value)[:180]
    return output


def capability_implementation_fingerprint(
    capability: "CapabilityDescriptor | dict[str, Any] | None",
) -> str:
    """Return a stable digest for execution-relevant capability identity.

    Readiness, permission, benchmark, load, pack counts and other live telemetry
    are intentionally excluded.  The fingerprint changes only when a node
    advertises a materially different runtime/model/tool/index implementation.
    Empty means the capability did not advertise enough stable identity to bind
    durable competence safely.
    """

    if capability is None:
        return ""
    if isinstance(capability, CapabilityDescriptor):
        name = str(capability.name or "").strip().casefold()
        metadata = dict(capability.metadata or {})
    elif isinstance(capability, dict):
        name = str(capability.get("name") or "").strip().casefold()
        raw = capability.get("metadata")
        metadata = dict(raw) if isinstance(raw, dict) else {}
    else:
        return ""

    explicit = str(metadata.get("implementation_fingerprint") or "").strip().lower()
    if explicit:
        if len(explicit) == 64 and all(ch in "0123456789abcdef" for ch in explicit):
            return explicit
        return sha256(("explicit:" + explicit).encode("utf-8")).hexdigest()

    stable: dict[str, Any] = {}
    for key in _IMPLEMENTATION_METADATA_KEYS:
        if key not in metadata:
            continue
        value = metadata.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, (bool, int, float, str)):
            stable[key] = value
        else:
            stable[key] = str(value)[:180]
    if not name or not stable:
        return ""
    encoded = json.dumps(
        {"capability": name, "implementation": stable},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CapabilityDescriptor:
    name: str
    available: bool = True
    private: bool = False
    local: bool = True
    cost: str = "free"
    latency: str = "interactive"
    readiness: str = "ready"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def routable(self) -> bool:
        return bool(self.available and str(self.readiness).strip().lower() in {"ready", "degraded"})

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityDescriptor":
        if not isinstance(payload, dict):
            raise ValueError("Capability advertisement must be a JSON object.")
        name = str(payload.get("name") or "").strip().lower()
        if not _CAPABILITY_NAME.fullmatch(name):
            raise ValueError("Capability name must use lowercase letters, numbers, '.', '_' or '-'.")
        cost = str(payload.get("cost") or "free").strip().lower()[:32] or "free"
        latency = str(payload.get("latency") or "interactive").strip().lower()[:32] or "interactive"
        readiness = str(payload.get("readiness") or ("ready" if payload.get("available", True) else "unavailable")).strip().lower()
        if readiness not in _READINESS:
            readiness = "ready" if bool(payload.get("available", True)) else "unavailable"
        return cls(
            name=name,
            available=bool(payload.get("available", True)),
            private=bool(payload.get("private", False)),
            local=bool(payload.get("local", True)),
            cost=cost,
            latency=latency,
            readiness=readiness,
            metadata=_safe_metadata(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        readiness = str(self.readiness or "ready").strip().lower()
        payload["readiness"] = readiness if readiness in _READINESS else "ready"
        if not self.available:
            payload["readiness"] = "unavailable"
        payload["routable"] = bool(self.available and payload["readiness"] in {"ready", "degraded"})
        payload["metadata"] = _safe_metadata(self.metadata)
        return payload


def capabilities_from_environment(environment: Any) -> list[CapabilityDescriptor]:
    """Create a display-safe local capability declaration from RuntimeEnvironment."""
    snapshot = dict(environment.snapshot() or {})
    raw = dict(snapshot.get("capabilities", {}) or {})
    output: list[CapabilityDescriptor] = []
    private_names = {"filesystem", "persistent_local_storage", "native_microphone", "native_audio"}
    for name, available in raw.items():
        output.append(
            CapabilityDescriptor(
                name=str(name),
                available=bool(available),
                private=str(name) in private_names,
                local=True,
                cost="free",
                latency="interactive",
            )
        )
    try:
        profile = RuntimeResourceProfile.detect()
        profile_data = profile.to_dict()
        resource_metadata = {
            "platform": profile_data.get("platform", "unknown"),
            "machine": profile_data.get("machine", "unknown"),
            "cpu_count": profile_data.get("cpu_count", 1),
            "memory_gib": profile_data.get("memory_gib", "unknown"),
            "apple_silicon": profile_data.get("apple_silicon", False),
            "ollama": profile_data.get("ollama_available", False),
            "llama_cpp": profile_data.get("llama_cpp_available", False),
            "whisper_cpp": profile_data.get("whisper_cpp_available", False),
        }
        try:
            from .resource_probe import observe_live_resources

            live = observe_live_resources()
            primary = live.primary_gpu
            if live.ram_free_gib is not None:
                resource_metadata["memory_free_gib"] = live.ram_free_gib
            resource_metadata["apple_unified_memory"] = live.apple_unified_memory
            if primary is not None:
                if primary.label:
                    resource_metadata["gpu_label_live"] = primary.label
                resource_metadata["gpu_backend"] = primary.backend
                resource_metadata["gpu_resource_source"] = primary.source
                if primary.total_gib is not None:
                    resource_metadata["gpu_memory_gib_live"] = primary.total_gib
                if primary.free_gib is not None:
                    resource_metadata["gpu_memory_free_gib"] = primary.free_gib
        except Exception:
            # Live resource telemetry is optional and must never make a node
            # unavailable merely because a vendor utility is absent or slow.
            pass
        output.append(
            CapabilityDescriptor(
                name="runtime.resource_profile",
                available=True,
                private=True,
                local=True,
                cost="free",
                latency="instant",
                metadata=resource_metadata,
            )
        )
        if profile.llama_cpp_available:
            output.append(
                CapabilityDescriptor(
                    name="llm.llama_cpp", available=True, private=True, local=True,
                    cost="local", latency="interactive",
                    metadata={"runtime": "llama.cpp"},
                )
            )
        if profile.apple_silicon:
            try:
                import importlib.util
                mlx_ready = importlib.util.find_spec("mlx") is not None and importlib.util.find_spec("mlx_lm") is not None
            except (ImportError, AttributeError, ValueError):
                mlx_ready = False
            if mlx_ready:
                output.append(
                    CapabilityDescriptor(
                        name="llm.mlx_lm", available=True, private=True, local=True,
                        cost="local", latency="interactive",
                        metadata={
                            "runtime": "mlx_lm",
                            "apple_silicon": True,
                            "adapter_loading": True,
                            "execution_authorized": False,
                        },
                    )
                )
    except Exception:
        pass

    providers = dict(snapshot.get("providers", {}) or {})
    for provider, data in providers.items():
        info = dict(data or {})
        if not bool(info.get("available")):
            continue
        local = str(provider).lower() == "ollama"
        output.append(
            CapabilityDescriptor(
                name=f"llm.{provider}",
                available=True,
                private=local,
                local=local,
                cost="local" if local else "provider_policy",
                latency="interactive",
                metadata={"model": info.get("model", "unknown")},
            )
        )
    return output
