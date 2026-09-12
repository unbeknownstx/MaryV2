"""Portable hardware/resource hints for replaceable Mary capability nodes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes.util
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
    metal_available: bool
    cuda_visible: bool
    vulkan_available: bool
    vulkan_tool_available: bool
    gpu_label: str
    gpu_memory_gib: float | None
    ollama_available: bool
    llama_cpp_available: bool
    whisper_cpp_available: bool

    @classmethod
    def detect(cls) -> "RuntimeResourceProfile":
        machine = platform.machine().lower()
        system = platform.system().lower()
        memory: int | None = None
        try:
            if system == "windows":
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                status = MEMORYSTATUSEX()
                status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    memory = int(status.ullTotalPhys)
            elif hasattr(os, "sysconf"):
                pages = int(os.sysconf("SC_PHYS_PAGES"))
                size = int(os.sysconf("SC_PAGE_SIZE"))
                memory = pages * size if pages > 0 and size > 0 else None
        except (OSError, ValueError, TypeError, AttributeError):
            memory = None

        apple_silicon = system == "darwin" and machine in {"arm64", "aarch64"}
        vulkan_tool = bool(shutil.which("vulkaninfo"))
        vulkan_loader = bool(
            ctypes.util.find_library("vulkan")
            or ctypes.util.find_library("vulkan-1")
            or (system == "windows" and os.path.exists(os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "vulkan-1.dll")))
        )
        gpu_label = os.getenv("MARY_NODE_GPU_LABEL", "").strip()[:160]
        gpu_memory: float | None = None
        try:
            raw_gpu_memory = os.getenv("MARY_NODE_GPU_MEMORY_GIB", "").strip()
            if raw_gpu_memory:
                gpu_memory = max(0.0, float(raw_gpu_memory))
        except ValueError:
            gpu_memory = None

        return cls(
            platform=system,
            machine=machine,
            cpu_count=max(1, int(os.cpu_count() or 1)),
            memory_bytes=memory,
            apple_silicon=apple_silicon,
            metal_available=apple_silicon,
            cuda_visible=bool(os.getenv("CUDA_VISIBLE_DEVICES", "").strip()),
            vulkan_available=vulkan_loader,
            vulkan_tool_available=vulkan_tool,
            gpu_label=gpu_label,
            gpu_memory_gib=gpu_memory,
            ollama_available=bool(shutil.which("ollama")),
            llama_cpp_available=bool(shutil.which("llama-server") or shutil.which("llama-cli")),
            whisper_cpp_available=bool(shutil.which("whisper-cli") or shutil.which("whisper.cpp")),
        )

    def recommended_policy(self) -> dict[str, Any]:
        if self.apple_silicon:
            return {
                "conversation": "cloud_first_or_small_local",
                "fast_brain": "small_local_metal",
                "stt": "whisper_cpp_metal_or_groq",
                "vad": "local",
                "tts": "elevenlabs_or_local",
                "training": "external",
                "vision": "small_local_on_demand_or_cloud",
                "background": "embeddings_indexing_summaries",
            }
        policy = {
            "conversation": "configured_router",
            "fast_brain": "small_local",
            "stt": "local_or_groq",
            "vad": "local",
            "tts": "configured",
            "training": "external_until_benchmarked",
            "vision": "on_demand",
            "background": "embeddings_indexing_summaries",
        }
        if self.vulkan_available:
            policy["gpu_acceleration"] = "benchmark_vulkan_for_llama_whisper_and_preprocessing"
        return policy

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["memory_bytes"] is not None:
            payload["memory_gib"] = round(payload["memory_bytes"] / (1024 ** 3), 2)
        payload["recommended_policy"] = self.recommended_policy()
        payload["authority"] = "capability_hint_only"
        return payload
