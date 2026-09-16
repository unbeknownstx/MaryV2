"""Read-only executable wiring audit for a live MaryV2 composition.

This module complements the object-identity integration graph.  It asks the
already-constructed runtime whether its persistence, routes, workspace,
providers, device broker, voice, presentation assets, MCP advertisements and
bounded action owner are actually reachable from the canonical composition.

The audit never sends a model request, executes a device/MCP task, approves a
tool mutation, or writes Mary's durable state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mary.runtime.integrity import application_integrity_report


_REQUIRED_PROTOCOL_ROUTES = frozenset({
    "/v1/health",
    "/v1/turn",
    "/v1/state",
    "/v1/dashboard",
    "/v1/workspace",
    "/v1/workspace/action",
    "/v1/memory/status",
    "/v1/conversation",
    "/v1/voice/status",
    "/v1/voice/synthesize",
    "/v1/nodes",
    "/v1/nodes/task/dispatch",
    "/v1/nodes/task/poll",
    "/v1/nodes/task/complete",
    "/v1/runtime/action",
})


def _bool_call(owner: Any, name: str) -> bool:
    return callable(getattr(owner, name, None))


def _safe_dict(callable_value: Any) -> dict[str, Any]:
    try:
        value = callable_value()
        return dict(value or {}) if isinstance(value, dict) else {}
    except Exception as exc:
        return {
            "_error": type(exc).__name__,
        }


def _persistence(application: Any) -> dict[str, Any]:
    mary = application.mary
    memory = getattr(mary, "memory", None)
    relationship = getattr(mary, "relationship", None)
    ecosystem = getattr(application, "ecosystem", None)
    workspace = _safe_dict(getattr(ecosystem, "workspace_snapshot", lambda: {}))
    semantics = dict(workspace.get("semantics", {}) or {})

    memory_path = getattr(memory, "storage_path", None)
    relationship_path = getattr(relationship, "path", None)
    app_memory_path = getattr(application, "memory_path", None)
    checks = {
        "memory_persistence_configured": memory_path is not None,
        "application_memory_matches_manager": (
            memory_path is not None
            and app_memory_path is not None
            and Path(memory_path) == Path(app_memory_path)
        ),
        "relationship_persistence_configured": relationship_path is not None,
        "canonical_workspace_projection": semantics.get("authority") == "canonical_workspace",
        "workspace_has_projects_tasks_owner": (
            isinstance(workspace.get("command"), dict)
            and _bool_call(getattr(ecosystem, "command", None), "create_project")
            and _bool_call(getattr(ecosystem, "command", None), "create_task")
        ),
    }
    return {
        "healthy": all(checks.values()),
        "checks": checks,
        "workspace_domains": sorted(
            key for key in (
                "command", "focus", "inbox", "study", "research", "production",
                "arcade", "presence", "current_work",
            )
            if key in workspace
        ),
    }


def _memory(application: Any) -> dict[str, Any]:
    mary = application.mary
    memory = getattr(mary, "memory", None)
    checks = {
        name: getattr(memory, name, None) is not None
        for name in ("working", "episodic", "semantic", "retrieval", "consolidation")
    }
    checks["turn_mind_uses_relationship"] = (
        getattr(getattr(mary, "turn_mind", None), "relationship", None)
        is getattr(mary, "relationship", None)
    )
    lifecycle = _safe_dict(getattr(mary, "memory_lifecycle_status", lambda: {}))
    return {
        "healthy": all(checks.values()),
        "checks": checks,
        "status_available": bool(lifecycle) and "_error" not in lifecycle,
        "lifecycle": lifecycle,
    }


def _providers(application: Any) -> dict[str, Any]:
    router = getattr(application.mary, "llm", None)
    routing = _safe_dict(getattr(router, "routing_status", lambda: {}))
    providers = [
        dict(item)
        for item in list(routing.get("providers", []) or [])
        if isinstance(item, dict)
    ]
    routes = dict(routing.get("routes", {}) or {})
    conversation_order = list(routes.get("conversation", []) or [])
    available = [
        str(item.get("provider") or "")
        for item in providers
        if bool(item.get("available"))
    ]
    return {
        "healthy": router is not None and bool(conversation_order),
        "router_connected": router is not None,
        "strategy": routing.get("strategy"),
        "conversation_order": conversation_order,
        "available_providers": available,
        "conversation_ready": bool(available),
        "provider_count": len(providers),
        "last_generation": dict(routing.get("last_generation", {}) or {}),
    }


def _nodes(application: Any, service: Any | None) -> dict[str, Any]:
    mary = application.mary
    registry = getattr(mary, "node_registry", None)
    snapshot = _safe_dict(getattr(registry, "snapshot", lambda: {}))
    nodes = [
        dict(item)
        for item in list(snapshot.get("nodes", []) or [])
        if isinstance(item, dict)
    ]
    live = [item for item in nodes if bool(item.get("connected")) and not bool(item.get("stale"))]
    advertised: set[str] = set()
    for item in live:
        capabilities = item.get("capabilities", {})
        if isinstance(capabilities, dict):
            advertised.update(str(name) for name in capabilities)
    broker = getattr(service, "device_tasks", None) if service is not None else None
    checks = {
        "registry_connected": registry is not None,
        "core_broker_connected": service is None or broker is not None,
        "ollama_adapter_connected": (
            service is None
            or getattr(service, "_device_ollama_provider", None) is not None
        ),
        "local_device_adapter_connected": (
            service is None
            or getattr(service, "_device_local_provider", None) is not None
        ),
    }
    return {
        "healthy": all(checks.values()),
        "checks": checks,
        "registered": len(nodes),
        "live": len(live),
        "live_capabilities": sorted(advertised),
        "local_llm_live": any(
            name in advertised
            for name in ("llm.local", "llm.ollama", "llm.llama_cpp")
        ),
        "mcp_live": sorted(name for name in advertised if name.startswith("mcp.")),
    }


def _protocol(service: Any | None) -> dict[str, Any]:
    if service is None:
        return {
            "healthy": True,
            "applicable": False,
            "missing_routes": [],
        }
    try:
        from mary.protocol.server import create_app

        api = create_app(service)
        paths = {str(getattr(route, "path", "")) for route in api.routes}
        missing = sorted(_REQUIRED_PROTOCOL_ROUTES - paths)
        return {
            "healthy": not missing,
            "applicable": True,
            "route_count": len(paths),
            "missing_routes": missing,
        }
    except Exception as exc:
        return {
            "healthy": False,
            "applicable": True,
            "route_count": 0,
            "missing_routes": sorted(_REQUIRED_PROTOCOL_ROUTES),
            "error_type": type(exc).__name__,
        }


def _voice(service: Any | None) -> dict[str, Any]:
    if service is None:
        return {
            "healthy": True,
            "applicable": False,
            "tts_ready": False,
            "stt_ready": False,
        }
    status = _safe_dict(getattr(service, "voice_status", lambda: {}))
    tts = dict(status.get("tts", {}) or {})
    stt = dict(status.get("stt", {}) or {})
    return {
        # Voice is optional; a disabled provider is a readiness degradation, not
        # a broken Core composition.
        "healthy": "_error" not in status,
        "applicable": True,
        "tts_ready": bool(tts.get("enabled") or tts.get("server_available")),
        "tts_provider": str(tts.get("provider") or "off"),
        "stt_ready": bool(stt.get("enabled") or stt.get("server_available")),
        "stt_provider": str(stt.get("provider") or "off"),
    }


def _avatar(application: Any) -> dict[str, Any]:
    mary = getattr(application, "mary", None)
    avatar = getattr(mary, "avatar", None)
    state = getattr(avatar, "state", None)

    config = getattr(mary, "config", None)
    paths = getattr(config, "paths", None)
    configured_root = getattr(paths, "root", None)
    root = Path(configured_root) if configured_root is not None else Path.cwd()

    assets: dict[str, Any] = {}
    try:
        from mary.desktop.frontend_build import avatar_asset_status

        assets = dict(avatar_asset_status(root))
    except Exception as exc:
        # Diagnostics must never make Core state/status fail merely because a
        # minimal composition has no Desktop asset tree or optional frontend
        # dependency. Report the unavailable readiness evidence instead.
        assets = {"error_type": type(exc).__name__}
    return {
        "healthy": avatar is None or state is not None,
        "applicable": avatar is not None,
        "bridge_connected": avatar is not None,
        "state_connected": state is not None,
        "vrm_configured": bool(assets.get("configured")),
        "vrm_public_ready": bool(assets.get("public_ready")),
        "vrm_built_ready": bool(assets.get("built_ready")),
        "vrm_source": str(assets.get("source") or "unknown"),
    }


def _actions(application: Any) -> dict[str, Any]:
    manager = getattr(application.mary, "tools", None)
    registry = getattr(manager, "registry", None)
    required = (
        "filesystem_read",
        "filesystem_write",
        "code_read",
        "code_apply_change",
        "web_search",
    )
    tool_checks = {
        name: bool(registry is not None and getattr(registry, "has", lambda _n: False)(name))
        for name in required
    }
    checks = {
        "tool_manager_connected": manager is not None,
        "approval_api_connected": (
            _bool_call(manager, "approve")
            and _bool_call(manager, "reject")
            and _bool_call(manager, "execute_approved")
        ),
        "required_tools_registered": all(tool_checks.values()),
    }
    autonomy = getattr(application.mary, "autonomy", None)
    checks["autonomy_connected"] = autonomy is not None
    return {
        "healthy": all(checks.values()),
        "checks": checks,
        "tools": tool_checks,
        "policy": "mutating tools require explicit approval; autonomy remains proposal-only",
    }


def build_runtime_wiring_audit(
    *,
    application: Any,
    service: Any | None = None,
) -> dict[str, Any]:
    """Return a secret-free live wiring/readiness snapshot."""

    composition = application_integrity_report(application)
    sections = {
        "composition": {
            "healthy": bool(composition.get("ok")),
            **composition,
        },
        "persistence": _persistence(application),
        "memory": _memory(application),
        "providers": _providers(application),
        "nodes": _nodes(application, service),
        "protocol": _protocol(service),
        "voice": _voice(service),
        "avatar": _avatar(application),
        "actions": _actions(application),
    }

    required_failures = [
        name
        for name, section in sections.items()
        if not bool(section.get("healthy"))
    ]
    degraded: list[str] = []
    if not sections["providers"].get("conversation_ready"):
        degraded.append("no_conversation_provider_currently_available")
    if service is not None and not sections["voice"].get("tts_ready"):
        degraded.append("core_tts_not_ready")
    if sections["avatar"].get("applicable") and not sections["avatar"].get("vrm_configured"):
        degraded.append("personal_vrm_not_configured")
    if service is not None and not sections["nodes"].get("local_llm_live"):
        degraded.append("no_live_local_llm_node")
    if service is not None and not sections["nodes"].get("mcp_live"):
        degraded.append("no_live_mcp_node")

    return {
        "healthy": not required_failures,
        "operational": (
            not required_failures
            and bool(sections["providers"].get("conversation_ready"))
        ),
        "required_failures": required_failures,
        "degraded": degraded,
        "sections": sections,
        "semantics": {
            "healthy": "required architecture is connected",
            "operational": "required architecture plus at least one live conversation route",
            "degraded": "optional/configuration-dependent capability is not currently ready",
            "external_calls": "no model/MCP/device execution is performed by this audit",
        },
    }
