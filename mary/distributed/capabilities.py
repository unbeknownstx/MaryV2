"""Capability descriptors for MaryV2 local/remote compute nodes.

Capabilities are descriptions of what a node can do, not permission grants.
The registry is intentionally transport-agnostic so the same model can later be
used by a cloud control plane, a home PC agent, or an embedded runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityDescriptor:
    name: str
    available: bool = True
    private: bool = False
    local: bool = True
    cost: str = "free"
    latency: str = "interactive"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = {
            str(key)[:80]: (str(value)[:180] if not isinstance(value, (bool, int, float)) else value)
            for key, value in list(self.metadata.items())[:16]
            if str(key).casefold() not in {"token", "api_key", "password", "secret", "authorization"}
        }
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
