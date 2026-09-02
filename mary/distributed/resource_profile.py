"""Portable hardware/resource hints for replaceable Mary capability nodes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import platform
import shutil
from typing import Any


@dataclass(frozen=True)
class RuntimeResourceProfile:
    platform: str
    machine: str
    cpu_count: int
    memory_bytes: int | None
    apple_silicon: bool
    cuda_visible: bool
    ollama_available: bool
    llama_cpp_available: bool
    whisper_cpp_available: bool

    @classmethod
    def detect(cls) -> "RuntimeResourceProfile":
        machine = platform.machine().lower()
        system = platform.system().lower()
        memory: int | None = None
        try:
            if hasattr(os, "sysconf"):
                pages = int(os.sysconf("SC_PHYS_PAGES"))
                size = int(os.sysconf("SC_PAGE_SIZE"))
                memory = pages * size if pages > 0 and size > 0 else None
        except (OSError, ValueError, TypeError):
            memory = None
        return cls(
            platform=system,
            machine=machine,
            cpu_count=max(1, int(os.cpu_count() or 1)),
            memory_bytes=memory,
            apple_silicon=system == "darwin" and machine in {"arm64", "aarch64"},
            cuda_visible=bool(os.getenv("CUDA_VISIBLE_DEVICES", "").strip()),
            ollama_available=bool(shutil.which("ollama")),
            llama_cpp_available=bool(shutil.which("llama-server") or shutil.which("llama-cli")),
            whisper_cpp_available=bool(shutil.which("whisper-cli") or shutil.which("whisper.cpp")),
        )

    def recommended_policy(self) -> dict[str, Any]:
        if self.apple_silicon:
            return {
                "conversation": "cloud_first_or_small_local",
                "fast_brain": "small_local_cpu_or_metal",
                "stt": "groq_or_whisper_cpp",
                "vad": "silero_onnx_or_sherpa_onnx",
                "tts": "elevenlabs_or_system",
                "training": "cloud_gpu",
                "vision": "cloud_or_small_local_on_demand",
            }
        return {
            "conversation": "configured_router",
            "fast_brain": "small_local",
            "stt": "groq_or_local",
            "vad": "silero_onnx",
            "tts": "configured",
            "training": "external_until_suitable_gpu",
            "vision": "on_demand",
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["memory_bytes"] is not None:
            payload["memory_gib"] = round(payload["memory_bytes"] / (1024 ** 3), 2)
        payload["recommended_policy"] = self.recommended_policy()
        payload["authority"] = "capability_hint_only"
        return payload
