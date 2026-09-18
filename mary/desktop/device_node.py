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

from mary.distributed import (
    CapabilityDescriptor,
    DeviceExecutionPermissions,
    ENGINEERING_CAPABILITIES,
    EngineeringWorker,
    MCP_CAPABILITIES,
    MCPFabric,
    engineering_capability_descriptors,
    sanitize_mcp_error,
)
from mary.llm.interface import (
    GenerationCost,
    GenerationOperation,
    GenerationPrivacy,
    GenerationRequest,
    LLMMessage,
    generation_correlation_id,
)
from mary.llm.providers.ollama import OllamaProvider
from mary.distributed.hardware_profiles import SAFE_LOCAL_MODEL, SAFE_LOCAL_NUM_CTX
from mary.distributed.model_artifacts import model_artifact_metadata_from_environment
from mary.llm.providers.llama_cpp import LlamaCppProvider
from mary.llm.providers.local_runtime import LocalRuntimeProvider
from mary.runtime.gateway import RemoteMaryGateway


def _ollama_model_for_role(role: str) -> str:
    """Resolve a concrete local model from a bounded role name.

    Core may request a role, never an arbitrary model ID. The device owns the
    role-to-model mapping so hardware upgrades do not require a Core rewrite.
    """

    general = os.getenv("MARY_OLLAMA_MODEL", SAFE_LOCAL_MODEL).strip() or SAFE_LOCAL_MODEL
    # Device-owned conversation override applies to all conversational lanes.
    # The Core may distinguish fast vs engaged/deep conversation semantically,
    # but a constrained node can intentionally keep both on the same smaller
    # local model without changing Mary's canonical state or Core policy.
    conversation = os.getenv("MARY_OLLAMA_CONVERSATION_MODEL", "").strip() or general
    utility = os.getenv("MARY_OLLAMA_UTILITY_MODEL", "").strip()
    explicit_fast = os.getenv("MARY_OLLAMA_FAST_MODEL", "").strip()
    # If conversation already has its own smaller/specialized model, preserve it
    # for fast dialogue. Otherwise a configured utility model may serve as the
    # bounded fast worker. An explicit FAST override always wins.
    fast = explicit_fast or (
        utility if utility and conversation == general else conversation
    )
    utility = utility or fast
    return {
        "general": general,
        "conversation": conversation,
        "fast": fast,
        "utility": utility,
    }.get(str(role or "general").strip().lower(), general)


def _select_ollama_context(
    *,
    prompt_characters: int,
    max_tokens: int,
    provider_num_ctx: int,
) -> tuple[int, int]:
    """Return (estimated_prompt_tokens, selected_ctx) within the device cap."""

    estimated_prompt_tokens = max(1, (max(0, int(prompt_characters)) + 2) // 3)
    required_ctx = estimated_prompt_tokens + max(1, int(max_tokens)) + 2048
    try:
        max_ctx = int(os.getenv("MARY_DEVICE_OLLAMA_MAX_CTX", str(SAFE_LOCAL_NUM_CTX)))
    except (TypeError, ValueError):
        max_ctx = SAFE_LOCAL_NUM_CTX
    # 4096 is intentionally supported only when a constrained device
    # explicitly caps itself there. Unconstrained/default nodes preserve the
    # established 8K minimum and may expand through the larger buckets.
    max_ctx = max(4096, min(65536, max_ctx))
    constrained_4k = max_ctx <= 4096
    base_floor = 4096 if constrained_4k else 8192
    base_ctx = max(base_floor, min(max_ctx, int(provider_num_ctx or base_floor)))
    target = max(base_ctx, required_ctx)
    buckets = (
        (4096,) if constrained_4k
        else (8192, 16384, 32768, 65536)
    )
    selected_ctx = next((size for size in buckets if size >= target), max_ctx)
    selected_ctx = min(selected_ctx, max_ctx)
    if required_ctx > selected_ctx:
        raise RuntimeError(
            "Local Mary prompt exceeds this device's bounded Ollama context "
            f"(estimated_required={required_ctx}, max_ctx={selected_ctx})."
        )
    return estimated_prompt_tokens, selected_ctx


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
            "hardware_profile": os.getenv("MARY_NODE_HARDWARE_PROFILE", "").strip() or "default",
            "num_ctx": int(getattr(provider, "num_ctx", SAFE_LOCAL_NUM_CTX) or SAFE_LOCAL_NUM_CTX),
            "max_ctx": int(os.getenv("MARY_DEVICE_OLLAMA_MAX_CTX", str(SAFE_LOCAL_NUM_CTX)) or SAFE_LOCAL_NUM_CTX),
        },
    )



def _llama_cpp_capability() -> CapabilityDescriptor | None:
    """Advertise llama.cpp only when the same local server executor is reachable."""

    provider = LlamaCppProvider()
    if not provider.is_available():
        return None
    artifact_metadata = model_artifact_metadata_from_environment(
        runtime="llama.cpp",
    )
    return CapabilityDescriptor(
        name="llm.llama_cpp",
        available=True,
        private=True,
        local=True,
        cost="local",
        latency="interactive",
        metadata={
            "configured_model": provider.model_name(),
            "runtime": "llama.cpp",
            "adapter_scales": bool(provider._lora_scales()),
            **artifact_metadata,
        },
    )


def _local_model_capability() -> CapabilityDescriptor | None:
    """Advertise the host's selected local conversation runtime under one stable capability."""

    provider = LocalRuntimeProvider(role="conversation")
    status = provider.runtime_status()
    if not bool(status.get("available")):
        return None
    model = str(status.get("model") or provider.model_name())[:160]
    runtime = str(status.get("runtime") or provider.runtime_name())[:64]
    fast_provider = LocalRuntimeProvider(role="fast")
    fast_status = fast_provider.runtime_status()
    fast_model = str(
        fast_status.get("model")
        or fast_provider.model_name()
        or model
    )[:160]
    fast_runtime = str(
        fast_status.get("runtime")
        or fast_provider.runtime_name()
        or runtime
    )[:64]
    return CapabilityDescriptor(
        name="llm.local",
        available=True,
        private=True,
        local=True,
        cost="local",
        latency="interactive",
        metadata={
            "runtime": runtime,
            "configured_model": model,
            "model_alias": model,
            "backing_model": (
                os.getenv("MARY_LM_STUDIO_BACKING_MODEL", "").strip()
                if runtime == "lm_studio"
                else model
            ),
            "general_model": model,
            "conversation_model": model,
            "fast_model": fast_model,
            "fast_runtime": fast_runtime,
            "utility_model": (
                os.getenv("MARY_OLLAMA_UTILITY_MODEL", "").strip()
                or fast_model
            ),
            "runtime_order": list(status.get("order") or []),
            "fast_runtime_order": list(fast_status.get("order") or []),
            "hardware_profile": os.getenv("MARY_NODE_HARDWARE_PROFILE", "").strip() or "default",
        },
    )

def desktop_capabilities(
    application: Any,
    bridge: Any,
    permissions: DeviceExecutionPermissions | None = None,
) -> list[CapabilityDescriptor]:
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

    # Only capabilities backed by DeviceCapabilityNodeAgent executors may be
    # routable. Presentation/device-presence features remain visible in node
    # diagnostics, but are explicitly non-routable so Core never dispatches a
    # task that this node cannot execute.
    items = [
        CapabilityDescriptor(
            "filesystem",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={
                "search_root_count": len(roots),
                "presentation_only": True,
            },
        ),
        CapabilityDescriptor(
            "personal_search",
            private=True,
            local=True,
            metadata={"search_root_count": len(roots)},
        ),
        CapabilityDescriptor(
            "creative_workspace",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={
                "workspace_selected": creative_configured,
                "presentation_only": True,
            },
        ),
        CapabilityDescriptor(
            "native_microphone",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={"presentation_only": True},
        ),
        CapabilityDescriptor(
            "native_audio",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={"presentation_only": True},
        ),
        CapabilityDescriptor(
            "desktop_ui",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={"presentation_only": True},
        ),
        CapabilityDescriptor(
            "avatar",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={"presentation_only": True},
        ),
        CapabilityDescriptor(
            "desktop_apps",
            available=False,
            private=True,
            local=True,
            readiness="unavailable",
            metadata={
                "available_app_count": available_apps,
                "presentation_only": True,
            },
        ),
    ]
    local_model = _local_model_capability()
    if local_model is not None:
        local_model.metadata["execution_authorized"] = bool(
            permissions is not None and permissions.is_allowed("llm.local")
        )
        items.append(local_model)
    ollama = _ollama_capability()
    if ollama is not None:
        ollama.metadata["execution_authorized"] = bool(
            permissions is not None and permissions.is_allowed("llm.ollama")
        )
        items.append(ollama)
    llama_cpp = _llama_cpp_capability()
    if llama_cpp is not None:
        llama_cpp.metadata["execution_authorized"] = bool(
            permissions is not None and permissions.is_allowed("llm.llama_cpp")
        )
        items.append(llama_cpp)
    if permissions is not None:
        items.extend(MCPFabric(permissions).capability_descriptors())
        items.extend(engineering_capability_descriptors(permissions))
    return items


def headless_local_llm_capabilities() -> list[CapabilityDescriptor]:
    """Return executable local-LLM capabilities for a headless device node."""

    items: list[CapabilityDescriptor] = []
    local_model = _local_model_capability()
    if local_model is not None:
        items.append(local_model)
    ollama = _ollama_capability()
    if ollama is not None:
        items.append(ollama)
    llama_cpp = _llama_cpp_capability()
    if llama_cpp is not None:
        items.append(llama_cpp)
    return items


def headless_node_capabilities(
    permissions: DeviceExecutionPermissions,
) -> list[CapabilityDescriptor]:
    """Return all configured bounded executors for a headless capability node."""

    local_items = headless_local_llm_capabilities()
    permission_names = {
        "llm.local": "llm.local",
        "llm.ollama": "llm.ollama",
        "llm.llama_cpp": "llm.llama_cpp",
    }
    for item in local_items:
        permission_name = permission_names.get(item.name)
        if permission_name:
            item.metadata["execution_authorized"] = bool(
                permissions.is_allowed(permission_name)
            )

    return [
        *local_items,
        *MCPFabric(permissions).capability_descriptors(),
        *engineering_capability_descriptors(permissions),
    ]


def headless_ollama_capabilities() -> list[CapabilityDescriptor]:
    """Compatibility name: return available headless local-LLM executors."""

    return headless_local_llm_capabilities()


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
        mcp_fabric: MCPFabric | None = None,
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
        self._mcp_fabric = mcp_fabric or MCPFabric(self.permissions)
        try:
            self._engineering_worker: EngineeringWorker | None = EngineeringWorker()
        except Exception:
            self._engineering_worker = None
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
            self._capabilities = desktop_capabilities(application, bridge, self.permissions)
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

    def refresh_capabilities(self) -> list[CapabilityDescriptor]:
        """Rebuild device capability metadata after a local permission change."""
        if self.application is not None and self.bridge is not None:
            self._capabilities = desktop_capabilities(
                self.application,
                self.bridge,
                self.permissions,
            )
        return list(self._capabilities)

    def refresh_registration(self) -> dict[str, Any]:
        self.refresh_capabilities()
        return self.register()

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
            "mcp": self._mcp_fabric.status(),
            "engineering": {
                "configured": self._engineering_worker is not None,
                "capabilities": sorted(
                    item.name for item in self._capabilities
                    if item.name in ENGINEERING_CAPABILITIES
                ),
                "policy": "typed repository tasks only; no generic shell; repository apply is separately permission-gated",
            },
            "execution_authorized": any(
                self.permissions.is_allowed(name)
                for name in ("llm.local", "llm.ollama", "llm.llama_cpp")
            ),
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

        if capability in MCP_CAPABILITIES:
            tool = str(dict(task.get("args") or {}).get("tool") or "").strip()
            if not self.permissions.is_mcp_tool_allowed(capability, tool):
                result = self.gateway.complete_capability_task(
                    task_id,
                    status="rejected",
                    error=f"Local MCP tool permission does not allow {capability}/{tool}.",
                )
                self._last_task["status"] = "rejected"
                return result

        started = monotonic()
        try:
            if capability == "personal_search":
                result_payload = self._execute_personal_search(dict(task.get("args") or {}))
            elif capability == "llm.local":
                result_payload = self._execute_local_model(dict(task.get("args") or {}))
            elif capability == "llm.ollama":
                result_payload = self._execute_ollama(dict(task.get("args") or {}))
            elif capability == "llm.llama_cpp":
                result_payload = self._execute_llama_cpp(dict(task.get("args") or {}))
            elif capability in ENGINEERING_CAPABILITIES:
                result_payload = self._execute_engineering(capability, dict(task.get("args") or {}))
            elif capability in MCP_CAPABILITIES:
                result_payload = self._execute_mcp(capability, dict(task.get("args") or {}))
            else:
                raise ValueError(f"No bounded device executor exists for {capability}.")
            result = self.gateway.complete_capability_task(
                task_id,
                status="completed",
                result=result_payload,
            )
            self._last_task["status"] = "completed"
            self._last_task["elapsed_ms"] = round((monotonic() - started) * 1000.0, 2)
            self._last_error = ""
            return result
        except Exception as exc:
            raw_error = f"{type(exc).__name__}: {exc}"
            error = sanitize_mcp_error(raw_error) if capability in MCP_CAPABILITIES else raw_error[:500]
            self._last_error = error
            self._last_task["status"] = "failed"
            self._last_task["elapsed_ms"] = round((monotonic() - started) * 1000.0, 2)
            self._last_task["error_type"] = type(exc).__name__
            try:
                return self.gateway.complete_capability_task(
                    task_id,
                    status="failed",
                    error=error,
                )
            except Exception:
                return {"ok": False, "error": error}


    def _execute_engineering(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run one typed repository task through the bounded local worker."""

        if self._engineering_worker is None:
            self._engineering_worker = EngineeringWorker()
        return self._engineering_worker.execute(capability, args)


    def _execute_mcp(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute one exact allow-listed tool on one configured MCP server."""

        tool = str(args.get("tool") or "").strip()
        arguments = args.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("MCP task arguments must be a JSON object.")
        return self._mcp_fabric.execute(
            capability,
            tool=tool,
            arguments=dict(arguments),
        )

    def _execute_local_model(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded generation through the host-selected local runtime."""

        raw_messages = list(args.get("messages") or [])
        if not raw_messages:
            raise ValueError("llm.local task requires messages.")
        role = str(args.get("role") or "general").strip().lower()
        if role not in {"general", "conversation", "fast", "utility"}:
            raise ValueError("Unsupported llm.local model role.")

        provider = LocalRuntimeProvider(role=role)
        if not provider.is_available():
            raise RuntimeError("No configured local model runtime is ready on this device.")

        messages = [
            LLMMessage(
                role=str(item.get("role") or "user"),
                content=str(item.get("content") or ""),
            )
            for item in raw_messages
            if isinstance(item, dict)
        ]
        if len(messages) != len(raw_messages):
            raise ValueError("llm.local task contains an invalid message.")

        max_tokens = max(1, min(2048, int(args.get("max_tokens", 1024))))
        generation_request = GenerationRequest(
            messages=tuple(messages),
            operation=(
                GenerationOperation.CONVERSATION.value
                if role in {"conversation", "fast"}
                else GenerationOperation.TASK_GENERATION.value
            ),
            privacy=GenerationPrivacy.LOCAL_ONLY.value,
            cost_class=GenerationCost.ZERO_LOCAL.value,
            correlation_id=generation_correlation_id("device-local"),
            purpose=f"device_local_{role}",
            temperature=float(args.get("temperature", 0.7)),
            max_tokens=max_tokens,
        )
        generation_timeout: float | None = None
        if role == "fast":
            try:
                generation_timeout = float(
                    os.getenv("MARY_DEVICE_LOCAL_FAST_GENERATION_TIMEOUT", "10")
                )
            except (TypeError, ValueError):
                generation_timeout = 10.0
            generation_timeout = max(3.0, min(30.0, generation_timeout))

        response = provider.generate_constrained(
            generation_request,
            timeout_seconds=generation_timeout,
        )
        content = str(response.content or "").strip()
        if not content:
            raise RuntimeError("Local model runtime returned an empty response.")
        if len(content) > 32_000:
            content = content[:31_999].rstrip() + "…"

        usage = dict(response.usage or {})
        safe_usage = {
            key: max(0, int(usage.get(key, 0) or 0))
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        return {
            "content": content,
            "provider": "local_device",
            "runtime": provider.runtime_name(),
            "model": str(response.model or provider.model_name())[:160],
            "finish_reason": str(response.finish_reason or "")[:80],
            "usage": safe_usage,
            "privacy": "generated on selected device; raw provider payload not returned",
        }

    def _execute_ollama(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded chat generation through the PC's configured Ollama."""

        raw_messages = list(args.get("messages") or [])
        if not raw_messages:
            raise ValueError("llm.ollama task requires messages.")

        role = str(args.get("role") or "general").strip().lower()
        if role not in {"general", "conversation", "fast", "utility"}:
            raise ValueError("Unsupported llm.ollama model role.")
        provider = OllamaProvider(model=_ollama_model_for_role(role))

        max_tokens = max(1, min(2048, int(args.get("max_tokens", 1024))))
        prompt_characters = sum(
            len(str(item.get("content") or ""))
            for item in raw_messages
            if isinstance(item, dict)
        )
        # Conservative token estimate plus explicit headroom. Constrained nodes
        # may deliberately cap context; oversized turns fail instead of silently
        # expanding GPU memory use.
        estimated_prompt_tokens, selected_ctx = _select_ollama_context(
            prompt_characters=prompt_characters,
            max_tokens=max_tokens,
            provider_num_ctx=int(getattr(provider, "num_ctx", SAFE_LOCAL_NUM_CTX) or SAFE_LOCAL_NUM_CTX),
        )
        provider.num_ctx = selected_ctx
        try:
            device_timeout = float(os.getenv("MARY_DEVICE_OLLAMA_GENERATION_TIMEOUT", "420"))
        except (TypeError, ValueError):
            device_timeout = 420.0
        provider.timeout = max(
            float(getattr(provider, "timeout", 180.0) or 180.0),
            max(30.0, min(600.0, device_timeout)),
        )
        self._last_task.update({
            "model": provider.model_name(),
            "prompt_characters": prompt_characters,
            "estimated_prompt_tokens": estimated_prompt_tokens,
            "num_ctx": selected_ctx,
            "max_tokens": max_tokens,
            "timeout_seconds": round(provider.timeout, 1),
        })

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
            max_tokens=max_tokens,
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

    def _execute_llama_cpp(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded generation through this node's configured llama.cpp server."""

        raw_messages = list(args.get("messages") or [])
        if not raw_messages:
            raise ValueError("llm.llama_cpp task requires messages.")
        role = str(args.get("role") or "general").strip().lower()
        if role not in {"general", "conversation", "fast", "utility"}:
            raise ValueError("Unsupported llm.llama_cpp model role.")
        provider = LlamaCppProvider()
        if not provider.is_available():
            raise RuntimeError("Configured llama.cpp provider is unavailable on this device.")
        messages = [
            LLMMessage(role=str(item.get("role") or "user"), content=str(item.get("content") or ""))
            for item in raw_messages if isinstance(item, dict)
        ]
        if len(messages) != len(raw_messages):
            raise ValueError("llm.llama_cpp task contains an invalid message.")
        response = provider.generate(
            messages,
            temperature=float(args.get("temperature", 0.7)),
            max_tokens=int(args.get("max_tokens", 1024)),
        )
        content = str(response.content or "").strip()
        if not content:
            raise RuntimeError("llama.cpp returned an empty response.")
        usage = dict(response.usage or {})
        return {
            "content": content[:32_000],
            "provider": "llama_cpp",
            "model": str(response.model or provider.model_name())[:160],
            "finish_reason": str(response.finish_reason or "")[:80],
            "usage": {key: max(0, int(usage.get(key, 0) or 0)) for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
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
