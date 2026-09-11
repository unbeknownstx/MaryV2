"""Device-local execution permissions for bounded Mary capability tasks."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from .mcp_fabric import MCP_CAPABILITIES, MCP_SERVER_CAPABILITIES, normalize_mcp_tool_name

_SAFE_CAPABILITIES = {"personal_search", "llm.ollama", "llm.llama_cpp", *MCP_CAPABILITIES}


def default_permission_path() -> Path:
    return Path.home() / ".maryv2" / "device_permissions.json"


def _normalize_server(value: str) -> str:
    server = str(value or "").strip().lower()
    if server.startswith("mcp."):
        server = server[4:]
    if server not in MCP_SERVER_CAPABILITIES:
        raise ValueError(f"Unsupported MCP server: {server}")
    return server


class DeviceExecutionPermissions:
    """Persistent local-only allow-lists. Default is deny-all.

    MCP execution intentionally has two gates: the capability itself must be
    allowed and the exact server/tool pair must also be allowed. Tool discovery
    never grants execution permission.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else default_permission_path()
        self._lock = RLock()

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return dict(raw) if isinstance(raw, dict) else {}

    def allowed(self) -> set[str]:
        with self._lock:
            raw = self._read()
            values = raw.get("allowed_capabilities", [])
            return {
                str(value).strip().lower()
                for value in values
                if str(value).strip().lower() in _SAFE_CAPABILITIES
            }

    def allowed_mcp_tools(self) -> dict[str, list[str]]:
        with self._lock:
            raw = self._read()
            source = raw.get("allowed_mcp_tools", {})
            if not isinstance(source, dict):
                return {}
            output: dict[str, list[str]] = {}
            for raw_server, raw_tools in source.items():
                try:
                    server = _normalize_server(str(raw_server))
                except ValueError:
                    continue
                if not isinstance(raw_tools, list):
                    continue
                tools: set[str] = set()
                for raw_tool in raw_tools[:256]:
                    try:
                        tools.add(normalize_mcp_tool_name(raw_tool))
                    except ValueError:
                        continue
                if tools:
                    output[server] = sorted(tools)
            return output

    def is_allowed(self, capability: str) -> bool:
        return str(capability or "").strip().lower() in self.allowed()

    def is_mcp_tool_allowed(self, server_or_capability: str, tool: str) -> bool:
        try:
            server = _normalize_server(server_or_capability)
            clean_tool = normalize_mcp_tool_name(tool)
        except ValueError:
            return False
        return clean_tool in set(self.allowed_mcp_tools().get(server, []))

    def allow(self, capability: str) -> dict[str, Any]:
        normalized = str(capability or "").strip().lower()
        if normalized not in _SAFE_CAPABILITIES:
            raise ValueError(f"Capability cannot be authorized by this build: {normalized}")
        values = self.allowed()
        values.add(normalized)
        self._write(values, self.allowed_mcp_tools())
        return self.status()

    def deny(self, capability: str) -> dict[str, Any]:
        normalized = str(capability or "").strip().lower()
        values = self.allowed()
        values.discard(normalized)
        self._write(values, self.allowed_mcp_tools())
        return self.status()

    def allow_mcp_tool(self, server_or_capability: str, tool: str) -> dict[str, Any]:
        server = _normalize_server(server_or_capability)
        clean_tool = normalize_mcp_tool_name(tool)
        mapping = self.allowed_mcp_tools()
        tools = set(mapping.get(server, []))
        tools.add(clean_tool)
        mapping[server] = sorted(tools)
        self._write(self.allowed(), mapping)
        return self.status()

    def deny_mcp_tool(self, server_or_capability: str, tool: str) -> dict[str, Any]:
        server = _normalize_server(server_or_capability)
        clean_tool = normalize_mcp_tool_name(tool)
        mapping = self.allowed_mcp_tools()
        tools = set(mapping.get(server, []))
        tools.discard(clean_tool)
        if tools:
            mapping[server] = sorted(tools)
        else:
            mapping.pop(server, None)
        self._write(self.allowed(), mapping)
        return self.status()

    def status(self) -> dict[str, Any]:
        values = sorted(self.allowed())
        return {
            "permission_file": str(self.path),
            "allowed_capabilities": values,
            "allowed_mcp_tools": self.allowed_mcp_tools(),
            "default": "deny",
            "mcp_policy": "capability allow + exact server/tool allow required",
            "supported": sorted(_SAFE_CAPABILITIES),
        }

    def _write(self, values: set[str], mcp_tools: dict[str, list[str]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": "13.4",
                "allowed_capabilities": sorted(values),
                "allowed_mcp_tools": {
                    server: sorted(set(tools))
                    for server, tools in sorted(mcp_tools.items())
                    if tools
                },
                "policy": "local device opt-in; MCP requires per-tool allowlist; no shell or arbitrary command execution",
            }
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
