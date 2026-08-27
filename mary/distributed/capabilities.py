"""Capability descriptors for MaryV2 local/remote compute nodes.

Capabilities are descriptions of what a node can do, not permission grants.
The registry is intentionally transport-agnostic so the same model can later be
used by a cloud control plane, a home PC agent, or an embedded runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

_CAPABILITY_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
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


@dataclass(frozen=True)
class CapabilityDescriptor:
    name: str
    available: bool = True
    private: bool = False
    local: bool = True
    cost: str = "free"
    latency: str = "interactive"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityDescriptor":
        if not isinstance(payload, dict):
            raise ValueError("Capability advertisement must be a JSON object.")
        name = str(payload.get("name") or "").strip().lower()
        if not _CAPABILITY_NAME.fullmatch(name):
            raise ValueError("Capability name must use lowercase letters, numbers, '.', '_' or '-'.")
        cost = str(payload.get("cost") or "free").strip().lower()[:32] or "free"
        latency = str(payload.get("latency") or "interactive").strip().lower()[:32] or "interactive"
        return cls(
            name=name,
            available=bool(payload.get("available", True)),
            private=bool(payload.get("private", False)),
            local=bool(payload.get("local", True)),
            cost=cost,
            latency=latency,
            metadata=_safe_metadata(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
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
