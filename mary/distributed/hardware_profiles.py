"""Canonical local-inference hardware profiles for Mary capability nodes."""
from __future__ import annotations

import os

SAFE_LOCAL_MODEL = "qwen3:1.7b"
SAFE_LOCAL_NUM_CTX = 4096
SAFE_LOCAL_KEEP_ALIVE = "10m"

HARDWARE_PROFILES: dict[str, dict[str, str]] = {
    "windows-rx580-4gb": {
        "MARY_OLLAMA_MODEL": SAFE_LOCAL_MODEL,
        "MARY_OLLAMA_CONVERSATION_MODEL": SAFE_LOCAL_MODEL,
        "MARY_OLLAMA_UTILITY_MODEL": SAFE_LOCAL_MODEL,
        "MARY_OLLAMA_NUM_CTX": str(SAFE_LOCAL_NUM_CTX),
        "MARY_DEVICE_OLLAMA_MAX_CTX": str(SAFE_LOCAL_NUM_CTX),
        "MARY_OLLAMA_KEEP_ALIVE": SAFE_LOCAL_KEEP_ALIVE,
        "MARY_OLLAMA_THINK": "false",
        "MARY_LOCAL_FAST_MAX_TOKENS": "96",
        "MARY_NODE_GPU_LABEL": "AMD Radeon RX 580",
        "MARY_NODE_GPU_MEMORY_GIB": "4",
    },
    "mac-apple-silicon": {
        "MARY_OLLAMA_MODEL": SAFE_LOCAL_MODEL,
        "MARY_OLLAMA_CONVERSATION_MODEL": SAFE_LOCAL_MODEL,
        "MARY_OLLAMA_UTILITY_MODEL": SAFE_LOCAL_MODEL,
        "MARY_OLLAMA_NUM_CTX": str(SAFE_LOCAL_NUM_CTX),
        "MARY_DEVICE_OLLAMA_MAX_CTX": str(SAFE_LOCAL_NUM_CTX),
        "MARY_OLLAMA_KEEP_ALIVE": SAFE_LOCAL_KEEP_ALIVE,
        "MARY_OLLAMA_THINK": "false",
        "MARY_LOCAL_FAST_MAX_TOKENS": "96",
        "MARY_NODE_GPU_LABEL": "Apple Silicon / Metal",
    },
}


def available_hardware_profiles() -> tuple[str, ...]:
    return tuple(sorted(HARDWARE_PROFILES))


def profile_values(name: str | None) -> dict[str, str]:
    normalized = str(name or "").strip().lower()
    if not normalized:
        return {}
    values = HARDWARE_PROFILES.get(normalized)
    if values is None:
        raise ValueError(f"Unsupported hardware profile: {normalized}")
    return dict(values)


def apply_hardware_profile(name: str | None) -> dict[str, str]:
    normalized = str(name or "").strip().lower()
    values = profile_values(normalized)
    if not normalized:
        return {}
    os.environ["MARY_NODE_HARDWARE_PROFILE"] = normalized
    for key, value in values.items():
        os.environ[key] = value
    return values
