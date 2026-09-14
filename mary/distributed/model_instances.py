"""Stable model-instance identities for Mary's replaceable cognition workers.

A model family name is not an execution identity. The same `qwen3:4b` can run
on several nodes, engines, contexts, and quantizations, with materially different
latency/correctness. This module gives those runtime instances stable qualified
IDs without granting them any Mary authority.

Capability truth precedence is explicit:
    measured > advertised > known metadata > heuristic > unknown

No model instance owns identity, memory, relationship, goals, or canonical state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from typing import Any, Iterable


VERSION = "13.47"
_LEVEL = {"unknown": 0, "heuristic": 1, "known": 2, "advertised": 3, "measured": 4}
_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._:@+\-]+")


def _segment(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = _SAFE_SEGMENT.sub("_", text)
    return text[:160] or fallback


@dataclass(frozen=True)
class CapabilityFact:
    value: Any
    source: str = "unknown"

    def __post_init__(self) -> None:
        source = str(self.source or "unknown").strip().lower()
        if source not in _LEVEL:
            source = "unknown"
        object.__setattr__(self, "source", source)

    @property
    def strength(self) -> int:
        return _LEVEL[self.source]

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "source": self.source}


def strongest_fact(*facts: CapabilityFact | None) -> CapabilityFact:
    candidates = [item for item in facts if isinstance(item, CapabilityFact)]
    if not candidates:
        return CapabilityFact(None, "unknown")
    # Stable: later equal-strength facts do not override earlier ones.
    return max(enumerate(candidates), key=lambda pair: (pair[1].strength, -pair[0]))[1]


@dataclass(frozen=True)
class ModelInstanceIdentity:
    node_id: str
    engine: str
    model: str
    variant: str = ""
    quantization: str = ""
    loaded_context: int | None = None
    trained_context: int | None = None
    capabilities: dict[str, CapabilityFact] = field(default_factory=dict)

    @property
    def qualified_id(self) -> str:
        base = f"{_segment(self.node_id)}/{_segment(self.engine)}/{_segment(self.model)}"
        suffix: list[str] = []
        if self.variant:
            suffix.append(_segment(self.variant))
        if self.quantization:
            suffix.append(_segment(self.quantization))
        return base + ("@" + "+".join(suffix) if suffix else "")

    @property
    def fingerprint(self) -> str:
        payload = {
            "node_id": self.node_id,
            "engine": self.engine,
            "model": self.model,
            "variant": self.variant,
            "quantization": self.quantization,
            "loaded_context": self.loaded_context,
            "trained_context": self.trained_context,
            "capabilities": {
                key: value.to_dict()
                for key, value in sorted(self.capabilities.items())
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        return sha256(encoded.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualified_id": self.qualified_id,
            "fingerprint": self.fingerprint,
            "node_id": self.node_id,
            "engine": self.engine,
            "model": self.model,
            "variant": self.variant,
            "quantization": self.quantization,
            "loaded_context": self.loaded_context,
            "trained_context": self.trained_context,
            "capabilities": {key: value.to_dict() for key, value in self.capabilities.items()},
            "authority": "replaceable_cognition_worker_only",
        }


def capability_fact(
    *,
    measured: Any = None,
    advertised: Any = None,
    known: Any = None,
    heuristic: Any = None,
) -> CapabilityFact:
    """Resolve a capability using explicit truth precedence.

    `None` means no evidence. False is a real measurement/advertisement and must
    beat weaker positive guesses.
    """
    ordered = (
        (measured, "measured"),
        (advertised, "advertised"),
        (known, "known"),
        (heuristic, "heuristic"),
    )
    for value, source in ordered:
        if value is not None:
            return CapabilityFact(value, source)
    return CapabilityFact(None, "unknown")


def model_instance_from_capability(
    *,
    node_id: str,
    capability_name: str,
    metadata: dict[str, Any] | None,
) -> ModelInstanceIdentity | None:
    """Project one LLM capability advertisement into a stable model instance."""
    name = str(capability_name or "").strip().lower()
    if not name.startswith("llm."):
        return None
    values = dict(metadata or {})
    engine = name.removeprefix("llm.") or "unknown"
    model = str(
        values.get("benchmark_model")
        or values.get("configured_model")
        or values.get("model")
        or "unknown"
    ).strip()
    if not model:
        model = "unknown"

    def _int(key: str) -> int | None:
        try:
            value = int(values.get(key) or 0)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    loaded_context = _int("loaded_context") or _int("num_ctx")
    trained_context = _int("trained_context") or _int("context_length")

    caps = {
        "tools": capability_fact(
            measured=values.get("measured_tools"),
            advertised=values.get("supports_tools"),
            known=values.get("known_tools"),
            heuristic=values.get("heuristic_tools"),
        ),
        "vision": capability_fact(
            measured=values.get("measured_vision"),
            advertised=values.get("supports_vision"),
            known=values.get("known_vision"),
            heuristic=values.get("heuristic_vision"),
        ),
        "thinking": capability_fact(
            measured=values.get("measured_thinking"),
            advertised=values.get("supports_thinking"),
            known=values.get("known_thinking"),
            heuristic=values.get("heuristic_thinking"),
        ),
        "embeddings": capability_fact(
            measured=values.get("measured_embeddings"),
            advertised=values.get("supports_embeddings"),
            known=values.get("known_embeddings"),
            heuristic=values.get("heuristic_embeddings"),
        ),
        "structured_json": capability_fact(
            measured=values.get("measured_structured_json"),
            advertised=values.get("supports_structured_json"),
            known=values.get("known_structured_json"),
            heuristic=values.get("heuristic_structured_json"),
        ),
    }

    return ModelInstanceIdentity(
        node_id=str(node_id or "unknown")[:96],
        engine=engine,
        model=model[:200],
        variant=str(values.get("variant") or "")[:120],
        quantization=str(values.get("quantization") or values.get("quant") or "")[:80],
        loaded_context=loaded_context,
        trained_context=trained_context,
        capabilities=caps,
    )


def instances_from_node_snapshot(snapshot: dict[str, Any] | None) -> list[ModelInstanceIdentity]:
    """Build model identities from a display-safe NodeRegistry snapshot."""
    output: list[ModelInstanceIdentity] = []
    for node in list(dict(snapshot or {}).get("nodes") or []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "unknown")
        capabilities = dict(node.get("capabilities") or {})
        for capability_name, raw in capabilities.items():
            if not isinstance(raw, dict):
                continue
            instance = model_instance_from_capability(
                node_id=node_id,
                capability_name=str(capability_name),
                metadata=dict(raw.get("metadata") or {}),
            )
            if instance is not None:
                output.append(instance)
    output.sort(key=lambda item: item.qualified_id)
    return output


class ModelInstanceRegistry:
    """Advisory registry that refuses ambiguous bare model names."""

    VERSION = VERSION

    def __init__(self, instances: Iterable[ModelInstanceIdentity] = ()) -> None:
        self._instances: dict[str, ModelInstanceIdentity] = {}
        for item in instances:
            self.register(item)

    def register(self, instance: ModelInstanceIdentity) -> ModelInstanceIdentity:
        self._instances[instance.qualified_id] = instance
        return instance

    def all(self) -> list[ModelInstanceIdentity]:
        return sorted(self._instances.values(), key=lambda item: item.qualified_id)

    def resolve(self, identifier: str) -> ModelInstanceIdentity:
        requested = str(identifier or "").strip()
        if requested in self._instances:
            return self._instances[requested]
        matches = [item for item in self._instances.values() if item.model == requested]
        if not matches:
            raise KeyError(f"Unknown model instance: {requested}")
        if len(matches) > 1:
            choices = ", ".join(sorted(item.qualified_id for item in matches))
            raise ValueError(f"Model name '{requested}' is ambiguous; use a qualified id: {choices}")
        return matches[0]

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "instances": [item.to_dict() for item in self.all()],
            "count": len(self._instances),
            "authority": "routing_identity_only",
        }
