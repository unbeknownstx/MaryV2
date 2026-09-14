"""Bounded live resource observation for replaceable Mary compute nodes.

This module is operational telemetry only. It never launches model workloads,
changes device permissions, or mutates Mary Core state. Host probes are fixed
commands with short timeouts and soft failure so startup cannot depend on a GPU
vendor utility being present.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import platform
import re
import shutil
import subprocess
from typing import Any, Callable, Sequence

VERSION = "13.40"
_MIB_PER_GIB = 1024.0


@dataclass(frozen=True)
class GPUObservation:
    label: str = ""
    total_gib: float | None = None
    free_gib: float | None = None
    backend: str = "unknown"
    source: str = "unknown"
    device_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveResourceObservation:
    platform: str
    ram_total_gib: float | None
    ram_free_gib: float | None
    gpus: tuple[GPUObservation, ...] = ()
    apple_unified_memory: bool = False
    probe_failures: tuple[str, ...] = ()
    authority: str = "operational_measurement_only"

    @property
    def primary_gpu(self) -> GPUObservation | None:
        if not self.gpus:
            return None
        return sorted(
            self.gpus,
            key=lambda item: (
                -(item.free_gib if item.free_gib is not None else -1.0),
                -(item.total_gib if item.total_gib is not None else -1.0),
                item.device_index,
            ),
        )[0]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        primary = self.primary_gpu
        payload["primary_gpu"] = primary.to_dict() if primary is not None else None
        return payload


def _gib_from_bytes(value: int | float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return round(number / (1024.0 ** 3), 3)


def _system_memory() -> tuple[float | None, float | None]:
    """Return total/free physical RAM without third-party dependencies."""
    system = platform.system().strip().lower()
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
                return _gib_from_bytes(status.ullTotalPhys), _gib_from_bytes(status.ullAvailPhys)
            return None, None

        if system == "linux":
            values: dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    key, _, rest = line.partition(":")
                    match = re.search(r"(\d+)", rest)
                    if match:
                        values[key] = int(match.group(1)) * 1024
            return _gib_from_bytes(values.get("MemTotal")), _gib_from_bytes(values.get("MemAvailable"))

        if system == "darwin":
            total = None
            free = None
            page_size = 4096
            try:
                total_text = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    timeout=0.35,
                    check=False,
                ).stdout.strip()
                total = _gib_from_bytes(int(total_text)) if total_text else None
            except (OSError, subprocess.SubprocessError, ValueError):
                total = None
            try:
                vm = subprocess.run(
                    ["vm_stat"],
                    capture_output=True,
                    text=True,
                    timeout=0.35,
                    check=False,
                ).stdout
                page_match = re.search(r"page size of (\d+) bytes", vm)
                if page_match:
                    page_size = int(page_match.group(1))
                counts = {}
                for key in ("Pages free", "Pages inactive", "Pages speculative"):
                    match = re.search(rf"{re.escape(key)}:\s+(\d+)", vm)
                    if match:
                        counts[key] = int(match.group(1))
                available_pages = sum(counts.values())
                if available_pages:
                    free = _gib_from_bytes(available_pages * page_size)
            except (OSError, subprocess.SubprocessError, ValueError):
                free = None
            return total, free
    except (OSError, ValueError, TypeError, AttributeError):
        return None, None
    return None, None


def _run_fixed(
    argv: Sequence[str],
    *,
    timeout: float = 0.75,
    runner: Callable[..., Any] = subprocess.run,
) -> str:
    completed = runner(
        list(argv),
        capture_output=True,
        text=True,
        timeout=max(0.1, min(2.0, float(timeout))),
        check=False,
    )
    if int(getattr(completed, "returncode", 1) or 0) != 0:
        raise RuntimeError("probe command failed")
    return str(getattr(completed, "stdout", "") or "")


def _probe_nvidia(*, runner: Callable[..., Any] = subprocess.run) -> tuple[GPUObservation, ...]:
    if not shutil.which("nvidia-smi"):
        return ()
    text = _run_fixed(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ],
        runner=runner,
    )
    items: list[GPUObservation] = []
    for index, line in enumerate(text.splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            total = round(max(0.0, float(parts[-2])) / _MIB_PER_GIB, 3)
            free = round(max(0.0, float(parts[-1])) / _MIB_PER_GIB, 3)
        except ValueError:
            continue
        items.append(
            GPUObservation(
                label=",".join(parts[:-2]).strip()[:160],
                total_gib=total,
                free_gib=min(total, free),
                backend="cuda",
                source="nvidia_smi",
                device_index=index,
            )
        )
    return tuple(items)


def _numbers_under_key(value: Any, needle: str) -> list[float]:
    output: list[float] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if needle in lowered:
                try:
                    output.append(float(item))
                    continue
                except (TypeError, ValueError):
                    pass
            output.extend(_numbers_under_key(item, needle))
    elif isinstance(value, list):
        for item in value:
            output.extend(_numbers_under_key(item, needle))
    return output


def _probe_rocm(*, runner: Callable[..., Any] = subprocess.run) -> tuple[GPUObservation, ...]:
    if not shutil.which("rocm-smi"):
        return ()
    text = _run_fixed(
        ["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"],
        runner=runner,
    )
    payload = json.loads(text or "{}")
    if not isinstance(payload, dict):
        return ()
    items: list[GPUObservation] = []
    for index, (_device, info) in enumerate(sorted(payload.items(), key=lambda item: str(item[0]))):
        if not isinstance(info, dict):
            continue
        labels = [
            str(value).strip()
            for key, value in info.items()
            if "card series" in str(key).casefold() or "card model" in str(key).casefold()
        ]
        total_values = _numbers_under_key(info, "vram total memory")
        used_values = _numbers_under_key(info, "vram total used memory")
        total_bytes = total_values[0] if total_values else None
        used_bytes = used_values[0] if used_values else None
        total = _gib_from_bytes(total_bytes)
        free = None
        if total_bytes is not None and used_bytes is not None:
            free = _gib_from_bytes(max(0.0, total_bytes - used_bytes))
        items.append(
            GPUObservation(
                label=(labels[0] if labels else str(_device))[:160],
                total_gib=total,
                free_gib=free,
                backend="rocm",
                source="rocm_smi",
                device_index=index,
            )
        )
    return tuple(items)


def _probe_windows_adapter_hint(
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[GPUObservation, ...]:
    """Get a total-memory hint only; Win32_VideoController has no live free VRAM."""
    if platform.system().strip().lower() != "windows":
        return ()
    executable = shutil.which("powershell") or shutil.which("powershell.exe")
    if not executable:
        return ()
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    )
    text = _run_fixed(
        [executable, "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=1.0,
        runner=runner,
    )
    payload = json.loads(text or "null")
    rows = payload if isinstance(payload, list) else [payload]
    items: list[GPUObservation] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        items.append(
            GPUObservation(
                label=str(row.get("Name") or "")[:160],
                total_gib=_gib_from_bytes(row.get("AdapterRAM")),
                free_gib=None,
                backend="windows_display",
                source="win32_videocontroller_hint",
                device_index=index,
            )
        )
    return tuple(items)


def _environment_hint() -> tuple[GPUObservation, ...]:
    label = os.getenv("MARY_NODE_GPU_LABEL", "").strip()
    raw = os.getenv("MARY_NODE_GPU_MEMORY_GIB", "").strip()
    if not label and not raw:
        return ()
    total = None
    if raw:
        try:
            total = max(0.0, float(raw))
        except ValueError:
            total = None
    return (
        GPUObservation(
            label=label[:160],
            total_gib=total,
            free_gib=None,
            backend="configured",
            source="environment_hint",
            device_index=0,
        ),
    )


def observe_live_resources(
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> LiveResourceObservation:
    """Collect bounded best-effort resource facts.

    Probe priority is measured vendor data first, then a platform adapter hint,
    then an explicit environment hint. Missing tooling is normal and never
    raises to the caller.
    """

    system = platform.system().strip().lower()
    machine = platform.machine().strip().lower()
    ram_total, ram_free = _system_memory()
    apple_unified = system == "darwin" and machine in {"arm64", "aarch64"}
    failures: list[str] = []
    gpus: tuple[GPUObservation, ...] = ()

    for name, probe in (
        ("nvidia", _probe_nvidia),
        ("rocm", _probe_rocm),
        ("windows", _probe_windows_adapter_hint),
    ):
        try:
            result = probe(runner=runner)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            failures.append(name)
            result = ()
        if result:
            gpus = result
            break

    if not gpus:
        gpus = _environment_hint()

    # Apple Silicon uses unified memory. Do not lie by copying system RAM into
    # a dedicated-VRAM field; the resource broker can reason from RAM separately.
    if apple_unified:
        gpus = tuple(
            GPUObservation(
                label=item.label,
                total_gib=None if item.source == "environment_hint" else item.total_gib,
                free_gib=None if item.source == "environment_hint" else item.free_gib,
                backend=item.backend,
                source=item.source,
                device_index=item.device_index,
            )
            for item in gpus
        )

    return LiveResourceObservation(
        platform=system,
        ram_total_gib=ram_total,
        ram_free_gib=ram_free,
        gpus=gpus,
        apple_unified_memory=apple_unified,
        probe_failures=tuple(failures),
    )


def resource_snapshot(
    node_id: str,
    *,
    loaded_models: Sequence[str] = (),
    active_realtime: bool = False,
    runner: Callable[..., Any] = subprocess.run,
):
    """Convert a live observation into the resource broker's planning shape."""
    from .resource_broker import ResourceSnapshot

    observation = observe_live_resources(runner=runner)
    primary = observation.primary_gpu
    return ResourceSnapshot(
        node_id=str(node_id or "local")[:96],
        ram_total_gb=observation.ram_total_gib,
        ram_free_gb=observation.ram_free_gib,
        vram_total_gb=(primary.total_gib if primary is not None else None),
        vram_free_gb=(primary.free_gib if primary is not None else None),
        loaded_models=tuple(str(item)[:180] for item in loaded_models),
        active_realtime=bool(active_realtime),
    )
