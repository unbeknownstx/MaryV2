"""Bounded provenance for operator-applied model-fit hints.

Fit hints remain explicit operator configuration. A provenance token lets a node
prove that a role-specific value was calibrated for the model/context it is now
advertising. Missing provenance preserves legacy explicit hints; mismatched or
malformed provenance suppresses only that role's hint.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

VERSION = "13.58"
_ROLES = ("general", "conversation", "fast", "utility")
_RUNTIME_PREFIX = {
    "ollama": "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB",
    "llama_cpp": "MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB",
}
_CAPABILITY_RUNTIME = {
    "llm.ollama": "ollama",
    "llm.llama_cpp": "llama_cpp",
}


def calibration_fingerprint(*, runtime: str, role: str, model: str, num_ctx: int | None) -> str:
    payload = {
        "runtime": str(runtime or "").strip().lower(),
        "role": str(role or "").strip().lower(),
        "model": str(model or "").strip(),
        "num_ctx": int(num_ctx or 0),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def provenance_env_name(runtime: str, role: str) -> str:
    prefix = _RUNTIME_PREFIX[str(runtime).strip().lower()]
    normalized_role = str(role or "").strip().lower()
    if normalized_role not in _ROLES:
        raise ValueError("role must be general, conversation, fast, or utility")
    return f"{prefix}_{normalized_role.upper()}_PROVENANCE"


def _configured_model(runtime: str, role: str) -> tuple[str, int | None] | None:
    try:
        if runtime == "ollama":
            from mary.desktop.device_node import _ollama_model_for_role
            from mary.llm.providers.ollama import OllamaProvider

            provider = OllamaProvider(model=_ollama_model_for_role(role))
        elif runtime == "llama_cpp":
            from mary.llm.providers.llama_cpp import LlamaCppProvider

            provider = LlamaCppProvider()
        else:
            return None
        return str(provider.model_name() or "").strip(), int(getattr(provider, "num_ctx", 0) or 0)
    except Exception:
        return None


def role_hint_is_current(capability: str, role: str, *, environ: Any = os.environ) -> bool:
    """Return False only when supplied provenance proves a hint is stale/invalid.

    Legacy explicit hints without provenance remain valid for compatibility.
    Once an operator applies a 13.58 provenance token, model/context drift causes
    the role hint to disappear until it is remeasured and explicitly reapplied.
    """
    runtime = _CAPABILITY_RUNTIME.get(str(capability or "").strip().lower())
    normalized_role = str(role or "").strip().lower()
    if runtime is None or normalized_role not in _ROLES:
        return True
    supplied = str(environ.get(provenance_env_name(runtime, normalized_role), "") or "").strip()
    if not supplied:
        return True
    configured = _configured_model(runtime, normalized_role)
    if configured is None:
        return False
    model, num_ctx = configured
    expected = calibration_fingerprint(
        runtime=runtime,
        role=normalized_role,
        model=model,
        num_ctx=num_ctx,
    )
    return supplied == expected
