"""Desktop capability-node advertisement for remote Mary Core mode.

This module describes what the current desktop can do. It does not expose an
execution server and it does not grant Mary permission to run those abilities.
"""
from __future__ import annotations

import json
import os
import platform
import socket
from threading import Event, Thread
from typing import Any
from urllib.request import Request, urlopen

from mary.distributed import CapabilityDescriptor
from mary.runtime.gateway import RemoteMaryGateway


def _ollama_capability() -> CapabilityDescriptor | None:
    enabled = os.getenv("MARY_OLLAMA_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if not enabled:
        return None

    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip() or "http://127.0.0.1:11434"
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    endpoint = host.rstrip("/") + "/api/tags"
    try:
        request = Request(endpoint, headers={"Accept": "application/json"})
        with urlopen(request, timeout=0.35) as response:
            raw = response.read(256_000)
        payload = json.loads(raw.decode("utf-8"))
        models = list(payload.get("models", []) or []) if isinstance(payload, dict) else []
    except Exception:
        return None

    return CapabilityDescriptor(
        name="llm.ollama",
        available=True,
        private=True,
        local=True,
        cost="local",
        latency="interactive",
        metadata={"model_count": len(models)},
    )


def desktop_capabilities(application: Any, bridge: Any) -> list[CapabilityDescriptor]:
    """Build a bounded, path-free advertisement of Desktop-local abilities."""

    roots = list(getattr(getattr(application, "ecosystem", None), "search", None).roots or []) if getattr(getattr(application, "ecosystem", None), "search", None) is not None else []
    integrations = []
    try:
        integrations = list(bridge.integrations.status())
    except Exception:
        integrations = []
    available_apps = sum(1 for item in integrations if bool(dict(item).get("available")))

    creative_configured = False
    try:
        creative_configured = bool(bridge.creative_workspace.configured)
    except Exception:
        pass

    items = [
        CapabilityDescriptor(
            "filesystem",
            private=True,
            local=True,
            metadata={"search_root_count": len(roots)},
        ),
        CapabilityDescriptor(
            "personal_search",
            private=True,
            local=True,
            metadata={"search_root_count": len(roots)},
        ),
        CapabilityDescriptor(
            "creative_workspace",
            private=True,
            local=True,
            metadata={"workspace_selected": creative_configured},
        ),
        CapabilityDescriptor("native_microphone", private=True, local=True),
        CapabilityDescriptor("native_audio", private=True, local=True),
        CapabilityDescriptor("desktop_ui", private=True, local=True),
        CapabilityDescriptor("avatar", private=True, local=True),
        CapabilityDescriptor(
            "desktop_apps",
            available=available_apps > 0,
            private=True,
            local=True,
            metadata={"available_app_count": available_apps},
        ),
    ]
    ollama = _ollama_capability()
    if ollama is not None:
        items.append(ollama)
    return items


class DesktopCapabilityNodeAgent:
    """Background registration + heartbeat client for one Desktop process."""

    def __init__(
        self,
        gateway: RemoteMaryGateway,
        *,
        application: Any,
        bridge: Any,
        heartbeat_seconds: float = 30.0,
    ) -> None:
        self.gateway = gateway
        self.application = application
        self.bridge = bridge
        self.heartbeat_seconds = max(10.0, float(heartbeat_seconds))
        self.display_name = (
            os.getenv("MARY_NODE_NAME", "").strip()
            or os.getenv("COMPUTERNAME", "").strip()
            or socket.gethostname().strip()
            or gateway.device_id
        )[:120]
        self.platform = {
            "darwin": "macos",
            "windows": "windows",
            "linux": "linux",
        }.get(platform.system().strip().lower(), platform.system().strip().lower() or "unknown")
        self._capabilities = desktop_capabilities(application, bridge)
        self._stop = Event()
        self._thread: Thread | None = None
        self._registered = False
        self._last_error = ""

    def registration_payload(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "host_type": "desktop",
            "platform": self.platform,
            "surface": "desktop",
            "capabilities": [item.to_dict() for item in self._capabilities],
            "local": True,
        }

    def register(self) -> dict[str, Any]:
        payload = self.registration_payload()
        result = self.gateway.register_node(**payload)
        self._registered = bool(result.get("ok", False))
        self._last_error = ""
        return result

    def heartbeat(self) -> dict[str, Any]:
        try:
            result = self.gateway.heartbeat_node()
            self._registered = bool(result.get("ok", False))
            self._last_error = ""
            return result
        except Exception:
            # Core may have restarted and forgotten ephemeral node state. A
            # fresh registration is the correct recovery; Mary state is not on
            # this device and is not affected.
            return self.register()

    def disconnect(self) -> dict[str, Any]:
        try:
            result = self.gateway.disconnect_node()
            self._registered = False
            return result
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._registered = False
            return {"ok": False, "error": self._last_error}

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="MaryDesktopNodeHeartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.5)
        self.disconnect()

    def status(self) -> dict[str, Any]:
        return {
            "node_id": self.gateway.device_id,
            "display_name": self.display_name,
            "registered": self._registered,
            "heartbeat_seconds": self.heartbeat_seconds,
            "capabilities": [item.to_dict() for item in self._capabilities],
            "execution_authorized": False,
            "last_error": self._last_error,
        }

    def _run(self) -> None:
        try:
            self.register()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
        while not self._stop.wait(self.heartbeat_seconds):
            try:
                self.heartbeat()
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
