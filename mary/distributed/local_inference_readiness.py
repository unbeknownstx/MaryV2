"""Read-only readiness probes for local inference runtimes."""
from __future__ import annotations

from importlib.util import find_spec
import os
from typing import Any


def _module(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def local_inference_status() -> dict[str, Any]:
    return {
        "version": "13.21",
        "ollama_configured": bool(os.getenv("MARY_OLLAMA_BASE_URL", "http://localhost:11434").strip()),
        "mlx_lm_installed": _module("mlx_lm"),
        "llama_cpp_python_installed": _module("llama_cpp"),
        "authority": "diagnostics_only",
        "startup_dependency": False,
    }
