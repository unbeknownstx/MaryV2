"""Desktop capability-node advertisement and bounded task executor.

The desktop advertises local capabilities to Mary Core. Core can queue narrowly
typed tasks, but the device executes only capabilities explicitly allowed by a
local permission file. There is no shell-command executor in this module.
"""
from __future__ import annotations

import json
import os
import platform
import socket
from threading import Event, Thread
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen

from mary.distributed import CapabilityDescriptor, DeviceExecutionPermissions
from mary.llm.interface import (
    GenerationCost,
    GenerationOperation,
    GenerationPrivacy,
    GenerationRequest,
    LLMMessage,
    generation_correlation_id,
)
from mary.llm.providers.ollama import OllamaProvider
from mary.runtime.gateway import RemoteMaryGateway


def _ollama_model_for_role(role: str) -> str:
    """Resolve a concrete local model from a bounded role name.

    Core may request a role, never an arbitrary model ID. The device owns the
    role-to-model mapping so hardware upgrades do not require a Core rewrite.
    """

    general = os.getenv("MARY_OLLAMA_MODEL", "qwen3:4b").strip() or "qwen3:4b"
    # Preserve Mary's existing local-role contract: the conversation override
    # is the latency-sensitive model used by conversation_fast/social lanes.
    # Engaged/deep conversation keeps the richer general model.
    conversation = general
    fast = os.getenv("MARY_OLLAMA_CONVERSATION_MODEL", "").strip() or general
    utility = os.getenv("MARY_OLLAMA_UTILITY_MODEL", "").strip() or fast
    return {
        "general": general,
        "conversation": conversation,
        "fast": fast,
        "utility": utility,
    }.get(str(role or "general").strip().lower(), general)


def _ollama_capability() -> CapabilityDescriptor | None:
    """Probe the same Ollama endpoint/model configuration used for execution."""

    provider = OllamaProvider()
    if not provider.is_available():
        return None

    endpoint = provider.base_url.rstrip("/") + "/api/tags"
    try:
        request = Request(endpoint, headers={"Accept": "application/json"})
        with urlopen(request, timeout=0.35) as response:
            raw = response.read(256_000)
        payload = json.loads(raw.decode("utf-8"))
        models = list(payload.get("models", []) or []) if isinstance(payload, dict) else []
    except Exception:
        models = []

    return CapabilityDescriptor(
        name="llm.ollama",
        available=True,
        private=True,
        local=True,
        cost="local",
        latency="interactive",
        metadata={
            "model_count": len(models),
            "configured_model": provider.model_name(),
            "general_model": _ollama_model_for_role("general"),
            "conversation_model": _ollama_model_for_role("conversation"),
            "fast_model": _ollama_model_for_role("fast"),
            "utility_model": _ollama_model_for_role("utility"),
        },
    )


def desktop_capabilities(application: Any, bridge: Any) -> list[CapabilityDescriptor]:
    """Build a bounded, path-free advertisement of Desktop-local abilities."""

    search = getattr(getattr(application, "ecosystem", None), "search", None)
    roots = list(getattr(search, "roots", []) or []) if search is not None else []
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


def headless_ollama_capabilities() -> list[CapabilityDescriptor]:
    """Return the bounded capabilities exposed by the headless Windows node.

    The headless node intentionally advertises only local Ollama. It does not
    imply that Desktop UI, microphone, filesystem, personal-search, or creative
    workspace capabilities are available while the GUI is closed.
    """

    ollama = _ollama_capability()
    return [ollama] if ollama is not None else []


class DesktopCapabilityNodeAgent:
    """Background registration, heartbeat, and bounded task polling."""

    def __init__(
        self,
        gateway: RemoteMaryGateway,
        *,
        application: Any | None = None,
        bridge: Any | None = None,
        capabilities: list[CapabilityDescriptor] | None = None,
        host_type: str = "desktop",
        surface: str = "desktop",
        heartbeat_seconds: float = 30.0,
        task_poll_seconds: float = 0.0,
        task_wait_seconds: float = 20.0,
        permissions: DeviceExecutionPermissions | None = None,
    ) -> None:
        self.gateway = gateway
        self.application = application
        self.bridge = bridge
        self.host_type = str(host_type or "desktop")[:80]
        self.surface = str(surface or "desktop")[:80]
        self.heartbeat_seconds = max(10.0, float(heartbeat_seconds))
        self.task_poll_seconds = max(0.0, float(task_poll_seconds))
        self.task_wait_seconds = max(1.0, min(25.0, float(task_wait_seconds)))
        self.permissions = permissions or DeviceExecutionPermissions()
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
        if capabilities is None:
            if application is None or bridge is None:
                raise ValueError(
                    "Desktop capability discovery requires application and bridge, "
                    "or an explicit bounded capabilities list."
                )
            self._capabilities = desktop_capabilities(application, bridge)
        else:
            self._capabilities = list(capabilities)
        self._stop = Event()
        self._thread: Thread | None = None
        self._registered = False
        self._last_error = ""
        self._last_task: dict[str, Any] = {}

    def registration_payload(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "host_type": self.host_type,
            "platform": self.platform,
            "surface": self.surface,
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
        self._thread = Thread(target=self._run, name="MaryDesktopCapabilityNode", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.75)
        self.disconnect()

    def status(self) -> dict[str, Any]:
        return {
            "node_id": self.gateway.device_id,
            "display_name": self.display_name,
            "registered": self._registered,
            "heartbeat_seconds": self.heartbeat_seconds,
            "task_poll_seconds": self.task_poll_seconds,
            "task_wait_seconds": self.task_wait_seconds,
            "task_delivery": "long_poll",
            "capabilities": [item.to_dict() for item in self._capabilities],
            "allowed_execution_capabilities": sorted(self.permissions.allowed()),
            "execution_authorized": False,
            "execution_default": "deny",
            "last_task": dict(self._last_task),
            "last_error": self._last_error,
        }

    def poll_once(self, *, wait_seconds: float | None = None) -> dict[str, Any]:
        wait = self.task_wait_seconds if wait_seconds is None else max(0.0, float(wait_seconds))
        payload = self.gateway.poll_capability_task(wait_seconds=wait)
        task = payload.get("task")
        if not isinstance(task, dict):
            return {"ok": True, "task": None}
        return self._handle_task(task)

    def _handle_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task.get("task_id") or "")
        capability = str(task.get("capability") or "").strip().lower()
        self._last_task = {
            "task_id": task_id,
            "capability": capability,
            "status": "received",
        }

        if not self.permissions.is_allowed(capability):
            result = self.gateway.complete_capability_task(
                task_id,
                status="rejected",
                error=f"Local device permission does not allow {capability}.",
            )
            self._last_task["status"] = "rejected"
            return result

        try:
            if capability == "personal_search":
                result_payload = self._execute_personal_search(dict(task.get("args") or {}))
            elif capability == "llm.ollama":
                result_payload = self._execute_ollama(dict(task.get("args") or {}))
            else:
                raise ValueError(f"No bounded device executor exists for {capability}.")
            result = self.gateway.complete_capability_task(
                task_id,
                status="completed",
                result=result_payload,
            )
            self._last_task["status"] = "completed"
            self._last_error = ""
            return result
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:500]
            self._last_error = error
            self._last_task["status"] = "failed"
            try:
                return self.gateway.complete_capability_task(
                    task_id,
                    status="failed",
                    error=error,
                )
            except Exception:
                return {"ok": False, "error": error}


    def _execute_ollama(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded chat generation through the PC's configured Ollama."""

        raw_messages = list(args.get("messages") or [])
        if not raw_messages:
            raise ValueError("llm.ollama task requires messages.")

        role = str(args.get("role") or "general").strip().lower()
        if role not in {"general", "conversation", "fast", "utility"}:
            raise ValueError("Unsupported llm.ollama model role.")
        provider = OllamaProvider(model=_ollama_model_for_role(role))
        if not provider.is_available():
            raise RuntimeError("Configured Ollama provider is unavailable on this device.")

        messages = [
            LLMMessage(
                role=str(item.get("role") or "user"),
                content=str(item.get("content") or ""),
            )
            for item in raw_messages
            if isinstance(item, dict)
        ]
        if len(messages) != len(raw_messages):
            raise ValueError("llm.ollama task contains an invalid message.")

        generation_request = GenerationRequest(
            messages=tuple(messages),
            operation=(
                GenerationOperation.CONVERSATION.value
                if role in {"conversation", "fast"}
                else GenerationOperation.TASK_GENERATION.value
            ),
            privacy=GenerationPrivacy.LOCAL_ONLY.value,
            cost_class=GenerationCost.ZERO_LOCAL.value,
            correlation_id=generation_correlation_id("device-ollama"),
            purpose=f"device_ollama_{role}",
            temperature=float(args.get("temperature", 0.7)),
            max_tokens=int(args.get("max_tokens", 1024)),
        )
        constrained = getattr(provider, "generate_constrained", None)
        if callable(constrained):
            response = constrained(generation_request)
        else:
            response = provider.generate(
                list(generation_request.messages),
                temperature=generation_request.temperature,
                max_tokens=generation_request.max_tokens,
            )
        content = str(response.content or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response.")
        if len(content) > 32_000:
            content = content[:31_999].rstrip() + "…"

        usage = dict(response.usage or {})
        safe_usage = {
            key: max(0, int(usage.get(key, 0) or 0))
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        return {
            "content": content,
            "provider": "ollama",
            "model": str(response.model or provider.model_name())[:160],
            "finish_reason": str(response.finish_reason or "")[:80],
            "usage": safe_usage,
            "privacy": "generated on selected device; raw provider payload not returned",
        }

    def _execute_personal_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = " ".join(str(args.get("query") or "").split())[:500]
        if not query:
            raise ValueError("personal_search task requires query.")
        limit = max(1, min(12, int(args.get("limit", 8) or 8)))
        if self.application is None:
            raise RuntimeError("Headless node does not expose personal_search.")
        search = getattr(getattr(self.application, "ecosystem", None), "search", None)
        if search is None:
            raise RuntimeError("Desktop personal search is unavailable.")
        raw = list(search.search(query, limit=limit) or [])
        items: list[dict[str, Any]] = []
        for item in raw[:limit]:
            values = dict(item or {})
            items.append({
                "name": str(values.get("name") or "")[:180],
                "relative_path": str(values.get("relative_path") or "")[:500],
                "kind": str(values.get("kind") or "file")[:40],
                "match": str(values.get("match") or "")[:40],
                "snippet": " ".join(str(values.get("snippet") or "").split())[:320],
            })
        return {
            "query": query,
            "count": len(items),
            "items": items,
            "privacy": "absolute paths and search roots omitted",
        }

    def _run(self) -> None:
        try:
            self.register()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"

        last_heartbeat = monotonic()
        while not self._stop.is_set():
            now = monotonic()
            if now - last_heartbeat >= self.heartbeat_seconds:
                try:
                    self.heartbeat()
                except Exception as exc:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                last_heartbeat = now
            try:
                # Keep one authenticated request parked at Core. Enqueue wakes
                # this request immediately, avoiding the old 0–2 second poll gap.
                self.poll_once(wait_seconds=self.task_wait_seconds)
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                # A restarted Core may have forgotten node registration. Recover
                # through the same outbound authenticated connection.
                try:
                    self.register()
                    last_heartbeat = monotonic()
                except Exception:
                    pass
            if self.task_poll_seconds > 0.0 and self._stop.wait(self.task_poll_seconds):
                break
