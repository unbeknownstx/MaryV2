"""Read-only readiness probes for local inference runtimes."""
from __future__ import annotations

from importlib.util import find_spec
import os
from typing import Any

from .inference_acceleration import local_acceleration_status
from .local_runtime_catalog import local_runtime_catalog


def _module(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def local_inference_status(
    *,
    model: str | None = None,
    runtime: str | None = None,
    gguf_nextn_predict_layers: int | None = None,
) -> dict[str, Any]:
    return {
        "version": "13.25",
        "ollama_configured": bool(os.getenv("MARY_OLLAMA_BASE_URL", "http://localhost:11434").strip()),
        "mlx_lm_installed": _module("mlx_lm"),
        "llama_cpp_python_installed": _module("llama_cpp"),
        "vllm_installed": _module("vllm"),
        "runtime_catalog": local_runtime_catalog(),
        "inference_acceleration": local_acceleration_status(
            model=model,
            runtime=runtime,
            gguf_nextn_predict_layers=gguf_nextn_predict_layers,
        ),
        "authority": "diagnostics_only",
        "startup_dependency": False,
    }
