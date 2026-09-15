"""Best-effort startup supervisor for Mary's desktop-local conversation runtime.

The desktop may use a replaceable local inference engine, but an engine failure
must never prevent Mary from opening. This module therefore performs only
bounded, reversible startup work: discover LM Studio, start its loopback server
when available, load an already-downloaded qualified model, and enable the
desktop capability-node bridge when a local runtime is ready.

It never downloads model weights, edits secrets, or makes a local engine an
identity/state authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

# Importing core config loads Mary's normal private .env location before the
# supervisor inspects runtime settings.
from mary.core.config import PathConfig  # noqa: F401
from mary.distributed import DeviceExecutionPermissions
from mary.llm.providers.local_runtime import LocalRuntimeProvider


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return True
    if raw in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _find_lms() -> str | None:
    discovered = shutil.which("lms") or shutil.which("lms.exe")
    if discovered:
        return discovered
    home = Path.home()
    names = ("lms.exe", "lms") if os.name == "nt" else ("lms", "lms.exe")
    for name in names:
        candidate = home / ".lmstudio" / "bin" / name
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


def _run(command: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1.0, float(timeout)),
        check=False,
        creationflags=(
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt"
            else 0
        ),
    )


def _json_output(result: subprocess.CompletedProcess[str]) -> Any:
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _model_is_downloaded(rows: Any, model_key: str) -> bool:
    if not isinstance(rows, list):
        return False
    wanted = str(model_key or "").strip()
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = {
            str(row.get("modelKey") or "").strip(),
            str(row.get("indexedModelIdentifier") or "").strip(),
            str(row.get("path") or "").strip(),
        }
        if wanted in values:
            return True
    return False


def _identifier_is_loaded(rows: Any, identifier: str) -> bool:
    if not isinstance(rows, list):
        return False
    wanted = str(identifier or "").strip()
    return any(
        isinstance(row, dict)
        and str(row.get("identifier") or "").strip() == wanted
        and str(row.get("status") or "").strip().lower() in {"idle", "loaded", "loading", "ready"}
        for row in rows
    )


def ensure_lm_studio_runtime() -> dict[str, Any]:
    """Start LM Studio and load Mary's already-installed conversation model."""

    if not _env_bool("MARY_LM_STUDIO_AUTOSTART", True):
        return {
            "runtime": "lm_studio",
            "ready": False,
            "state": "autostart_disabled",
        }

    executable = _find_lms()
    if not executable:
        return {
            "runtime": "lm_studio",
            "ready": False,
            "state": "cli_not_found",
        }

    identifier = (
        os.getenv("MARY_LM_STUDIO_IDENTIFIER", "").strip()
        or os.getenv("MARY_LM_STUDIO_MODEL", "").strip()
        or "mary-conversation"
    )
    load_model = (
        os.getenv("MARY_LM_STUDIO_LOAD_MODEL", "").strip()
        or "qwen/qwen3-4b-2507"
    )
    context = os.getenv("MARY_LM_STUDIO_CONTEXT", "4096").strip() or "4096"
    gpu = os.getenv("MARY_LM_STUDIO_GPU", "max").strip() or "max"

    try:
        status = _run([executable, "status"], timeout=8.0)
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "runtime": "lm_studio",
            "ready": False,
            "state": "status_failed",
            "error_type": type(exc).__name__,
        }

    server_on = status.returncode == 0 and "SERVER: ON" in (status.stdout or "").upper()
    if not server_on:
        try:
            started = _run([executable, "server", "start"], timeout=20.0)
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "runtime": "lm_studio",
                "ready": False,
                "state": "server_start_failed",
                "error_type": type(exc).__name__,
            }
        if started.returncode != 0:
            return {
                "runtime": "lm_studio",
                "ready": False,
                "state": "server_start_failed",
                "detail": (started.stderr or started.stdout or "")[:240],
            }

    try:
        loaded = _json_output(_run([executable, "ps", "--json"], timeout=8.0))
    except (OSError, subprocess.SubprocessError):
        loaded = None

    if not _identifier_is_loaded(loaded, identifier):
        try:
            library = _json_output(_run([executable, "ls", "--json"], timeout=10.0))
        except (OSError, subprocess.SubprocessError):
            library = None
        if not _model_is_downloaded(library, load_model):
            return {
                "runtime": "lm_studio",
                "ready": False,
                "state": "model_not_downloaded",
                "model": load_model,
                "identifier": identifier,
            }

        command = [
            executable,
            "load",
            load_model,
            "--context-length",
            context,
            "--gpu",
            gpu,
            "--identifier",
            identifier,
        ]
        try:
            loaded_result = _run(command, timeout=90.0)
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "runtime": "lm_studio",
                "ready": False,
                "state": "model_load_failed",
                "model": load_model,
                "identifier": identifier,
                "error_type": type(exc).__name__,
            }
        if loaded_result.returncode != 0:
            return {
                "runtime": "lm_studio",
                "ready": False,
                "state": "model_load_failed",
                "model": load_model,
                "identifier": identifier,
                "detail": (loaded_result.stderr or loaded_result.stdout or "")[:240],
            }

    os.environ.setdefault("MARY_LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    os.environ["MARY_LM_STUDIO_MODEL"] = identifier
    os.environ["MARY_LM_STUDIO_BACKING_MODEL"] = load_model
    if os.getenv("MARY_LOCAL_INFERENCE_RUNTIME", "auto").strip().lower() in {"", "auto"}:
        os.environ["MARY_LOCAL_INFERENCE_RUNTIME"] = "lm_studio"

    provider = LocalRuntimeProvider(role="conversation")
    runtime_status = provider.runtime_status()
    return {
        "runtime": "lm_studio",
        "ready": bool(runtime_status.get("available")),
        "state": "ready" if runtime_status.get("available") else "endpoint_not_ready",
        "model": str(runtime_status.get("model") or identifier),
        "backing_model": load_model,
        "identifier": identifier,
        "base_url": os.environ["MARY_LM_STUDIO_BASE_URL"],
    }


def prepare_desktop_runtime() -> dict[str, Any]:
    """Prepare a usable local conversation lane without blocking desktop startup.

    Creator Desktop product mode is intentionally local-first. When a bounded
    ``llm.local`` runtime is actually reachable, the default product behavior is
    to authorize *only that capability* on this same host so opening Mary is
    sufficient to use it. ``MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE=false``
    remains an explicit opt-out and every other filesystem/MCP/sensor/tool
    permission keeps its normal deny-by-default boundary.
    """

    configured = os.getenv("MARY_LOCAL_INFERENCE_RUNTIME", "auto").strip().lower() or "auto"
    lm_status: dict[str, Any] = {
        "runtime": "lm_studio",
        "ready": False,
        "state": "not_requested",
    }
    if configured in {"auto", "lm_studio"}:
        try:
            lm_status = ensure_lm_studio_runtime()
        except Exception as exc:
            lm_status = {
                "runtime": "lm_studio",
                "ready": False,
                "state": "startup_error",
                "error_type": type(exc).__name__,
            }

    provider = LocalRuntimeProvider(role="conversation")
    try:
        local_status = provider.runtime_status()
    except Exception as exc:
        local_status = {
            "available": False,
            "runtime": "",
            "model": "",
            "role": "conversation",
            "error_type": type(exc).__name__,
        }

    ready = bool(local_status.get("available"))
    local_compute_enabled = _env_bool("MARY_DESKTOP_LOCAL_COMPUTE", True)
    auto_authorize = _env_bool("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", True)
    local_authorized = False
    if ready and local_compute_enabled:
        # Product mode: the desktop can host its bounded capability node so
        # opening Mary is sufficient for local conversation. Dedicated headless
        # home-node mode remains available for always-on/mobile use.
        os.environ.setdefault("MARY_DESKTOP_CAPABILITY_NODE_ENABLED", "true")

        if auto_authorize:
            try:
                permissions = DeviceExecutionPermissions()
                permissions.allow("llm.local")
                local_authorized = bool(permissions.is_allowed("llm.local"))
            except Exception:
                local_authorized = False
        else:
            try:
                local_authorized = bool(DeviceExecutionPermissions().is_allowed("llm.local"))
            except Exception:
                local_authorized = False

    return {
        "ready": ready,
        "local": local_status,
        "lm_studio": lm_status,
        "local_compute_enabled": local_compute_enabled,
        "local_compute_auto_authorize": auto_authorize,
        "local_compute_authorized": local_authorized,
        "capability_node_enabled": os.getenv(
            "MARY_DESKTOP_CAPABILITY_NODE_ENABLED",
            "false",
        ).strip().lower() in {"1", "true", "yes", "on"},
        "authority": "runtime_only",
    }
