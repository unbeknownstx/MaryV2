"""Bounded MCP client fabric for MaryV2 capability nodes.

Mary Core never connects to MCP servers directly. A registered device node may
advertise one of the explicitly supported MCP capabilities and execute a typed
tool call only after both the capability and the exact tool name have been
allowed in the node-local permission store.

Configuration and credentials remain node-local. Core tasks contain only a
server capability, tool name, and sanitized tool arguments. No stdio process
launcher or arbitrary command execution is provided here; the fabric connects
only to explicitly configured Streamable HTTP(S) MCP endpoints.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import importlib.util
import json
import os
import re
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from .capabilities import CapabilityDescriptor

MCP_CAPABILITIES = frozenset({"mcp.opendesign", "mcp.scrapling", "mcp.langflow"})
MCP_SERVER_CAPABILITIES = {
    "opendesign": "mcp.opendesign",
    "scrapling": "mcp.scrapling",
    "langflow": "mcp.langflow",
}
MCP_CAPABILITY_SERVERS = {value: key for key, value in MCP_SERVER_CAPABILITIES.items()}
_TOOL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "cookie",
    "set_cookie",
    "credential",
    "credentials",
    "private_key",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]{12,}={0,2}"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]{8,}"),
    re.compile(r"(?i)([?&](?:access_token|api_key|apikey|token|secret|key)=)[^&#\s]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


def _normalized_server(value: str) -> str:
    server = str(value or "").strip().lower()
    if server.startswith("mcp."):
        server = server[4:]
    if server not in MCP_SERVER_CAPABILITIES:
        raise ValueError(f"Unsupported MCP server: {server}")
    return server


def normalize_mcp_tool_name(value: Any) -> str:
    tool = str(value or "").strip()
    if not _TOOL_NAME.fullmatch(tool):
        raise ValueError("MCP tool name must be 1-128 safe identifier characters.")
    return tool


def _is_secret_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in _SECRET_KEYS or normalized.endswith("_secret") or normalized.endswith("_token")


def _redact_string(value: Any, *, limit: int) -> str:
    text = str(value or "")
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", text)
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "…"
    return text


def sanitize_mcp_error(value: Any) -> str:
    """Return a bounded diagnostic string without node-local secrets or full MCP URLs."""

    text = str(value or "")
    # Collapse exact node-local endpoint values before generic token redaction.
    # Otherwise redacting a query token can mutate the URL and prevent the
    # endpoint replacement from matching, leaving userinfo/path material behind.
    for server in MCP_SERVER_CAPABILITIES:
        raw_url = os.getenv(f"MARY_MCP_{server.upper()}_URL", "").strip()
        if not raw_url or raw_url not in text:
            continue
        try:
            parsed = urlparse(raw_url)
            host = parsed.hostname or "configured"
            if parsed.port:
                host = f"{host}:{parsed.port}"
            summary = f"{parsed.scheme}://{host}"
        except Exception:
            summary = "[CONFIGURED-MCP-ENDPOINT]"
        text = text.replace(raw_url, summary)
    return _redact_string(text, limit=500)


def _sanitize_value(
    value: Any,
    *,
    reject_secrets: bool,
    depth: int = 0,
    max_depth: int = 8,
    max_items: int = 64,
    string_limit: int = 16_000,
) -> Any:
    if depth > max_depth:
        raise ValueError("MCP payload nesting exceeds the bounded depth limit.")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if reject_secrets:
            redacted = _redact_string(value, limit=string_limit)
            if "[REDACTED]" in redacted:
                raise ValueError("MCP task arguments may not carry credentials or bearer tokens.")
            return redacted
        return _redact_string(value, limit=string_limit)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:max_items]:
            key = str(raw_key or "").strip()[:128]
            if not key:
                continue
            if _is_secret_key(key):
                if reject_secrets:
                    raise ValueError(f"MCP task arguments may not include secret field: {key}")
                output[key] = "[REDACTED]"
                continue
            output[key] = _sanitize_value(
                raw_value,
                reject_secrets=reject_secrets,
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
                string_limit=string_limit,
            )
        return output
    if isinstance(value, (list, tuple)):
        return [
            _sanitize_value(
                item,
                reject_secrets=reject_secrets,
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
                string_limit=string_limit,
            )
            for item in list(value)[:max_items]
        ]
    return _redact_string(value, limit=min(string_limit, 2_000))


def sanitize_mcp_task_args(capability: str, args: dict[str, Any] | None) -> dict[str, Any]:
    normalized = str(capability or "").strip().lower()
    if normalized not in MCP_CAPABILITIES:
        raise ValueError(f"Unsupported MCP capability: {normalized}")
    values = dict(args or {})
    tool = normalize_mcp_tool_name(values.get("tool"))
    arguments = values.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("MCP task arguments must be a JSON object.")
    safe_arguments = _sanitize_value(arguments, reject_secrets=True)
    encoded = json.dumps(safe_arguments, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > 48_000:
        raise ValueError("MCP task arguments exceed the 48000 character limit.")
    return {"tool": tool, "arguments": safe_arguments}


def sanitize_mcp_result(capability: str, result: dict[str, Any] | None) -> dict[str, Any]:
    normalized = str(capability or "").strip().lower()
    server = MCP_CAPABILITY_SERVERS.get(normalized)
    if server is None:
        raise ValueError(f"Unsupported MCP capability: {normalized}")
    values = dict(result or {})
    tool = ""
    if values.get("tool"):
        try:
            tool = normalize_mcp_tool_name(values.get("tool"))
        except ValueError:
            tool = "invalid-tool-name"
    safe = _sanitize_value(values, reject_secrets=False, string_limit=24_000)
    if not isinstance(safe, dict):
        safe = {}
    for key in list(safe):
        if str(key).strip().lower() in {"url", "endpoint", "headers", "auth", "authentication"}:
            safe.pop(key, None)
    safe["server"] = server
    if tool:
        safe["tool"] = tool
    safe["privacy"] = "sanitized MCP result; node credentials and endpoint configuration are not returned to Core"
    encoded = json.dumps(safe, ensure_ascii=False, default=str)
    if len(encoded) <= 64_000:
        return safe
    return {
        "server": server,
        "tool": tool,
        "content": _redact_string(encoded, limit=63_000),
        "truncated": True,
        "privacy": safe["privacy"],
    }


@dataclass(frozen=True)
class MCPServerConfig:
    server: str
    capability: str
    url: str
    headers: dict[str, str]
    timeout_seconds: float = 30.0

    @property
    def endpoint_scope(self) -> str:
        parsed = urlparse(self.url)
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return "loopback"
        return "remote"

    @property
    def endpoint_summary(self) -> str:
        parsed = urlparse(self.url)
        host = parsed.hostname or "configured"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{host}"


class MCPTransport(Protocol):
    def list_tools(self, config: MCPServerConfig) -> list[str]: ...
    def call_tool(self, config: MCPServerConfig, tool: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


def mcp_dependency_available() -> bool:
    return importlib.util.find_spec("mcp") is not None


def _headers_from_environment(server: str) -> dict[str, str]:
    prefix = f"MARY_MCP_{server.upper()}"
    raw = os.getenv(f"{prefix}_HEADERS_JSON", "").strip()
    headers: dict[str, str] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{prefix}_HEADERS_JSON must contain a JSON object.") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{prefix}_HEADERS_JSON must contain a JSON object.")
        for key, value in list(parsed.items())[:16]:
            clean_key = str(key or "").strip()[:120]
            clean_value = str(value or "").strip()
            if clean_key and clean_value:
                headers[clean_key] = clean_value
    api_key = os.getenv(f"{prefix}_API_KEY", "").strip()
    bearer = os.getenv(f"{prefix}_BEARER_TOKEN", "").strip()
    if api_key:
        headers.setdefault("x-api-key", api_key)
    if bearer:
        headers.setdefault("Authorization", f"Bearer {bearer}")
    return headers


def server_config_from_environment(server: str) -> MCPServerConfig | None:
    normalized = _normalized_server(server)
    prefix = f"MARY_MCP_{normalized.upper()}"
    url = os.getenv(f"{prefix}_URL", "").strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{prefix}_URL must be an http(s) MCP endpoint URL.")
    host = (parsed.hostname or "").lower()
    insecure_remote = parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}
    if insecure_remote and os.getenv("MARY_MCP_ALLOW_INSECURE_REMOTE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        raise ValueError(
            f"{prefix}_URL uses plaintext HTTP on a non-loopback host; use HTTPS or explicitly set MARY_MCP_ALLOW_INSECURE_REMOTE=true."
        )
    try:
        timeout = float(os.getenv(f"{prefix}_TIMEOUT_SECONDS", "30") or 30)
    except (TypeError, ValueError):
        timeout = 30.0
    return MCPServerConfig(
        server=normalized,
        capability=MCP_SERVER_CAPABILITIES[normalized],
        url=url,
        headers=_headers_from_environment(normalized),
        timeout_seconds=max(2.0, min(120.0, timeout)),
    )


class _SDKMCPTransport:
    """Optional MCP SDK transport. Imported only when a configured call is made."""

    @staticmethod
    async def _with_client(config: MCPServerConfig, operation: Callable[[Any], Any]) -> Any:
        try:
            from mcp import Client
        except ImportError as exc:
            raise RuntimeError(
                "MCP client support is not installed on this node. Install requirements-node-mcp.txt."
            ) from exc

        if config.headers:
            try:
                import httpx2
                from mcp.client.streamable_http import streamable_http_client
            except ImportError as exc:
                raise RuntimeError("Configured MCP authentication requires the MCP SDK HTTP transport dependencies.") from exc
            timeout = httpx2.Timeout(config.timeout_seconds, read=config.timeout_seconds)
            async with httpx2.AsyncClient(headers=config.headers, timeout=timeout) as http_client:
                transport = streamable_http_client(config.url, http_client=http_client)
                async with Client(transport, read_timeout_seconds=config.timeout_seconds) as client:
                    return await operation(client)
        async with Client(config.url, read_timeout_seconds=config.timeout_seconds) as client:
            return await operation(client)

    def list_tools(self, config: MCPServerConfig) -> list[str]:
        async def operation(client: Any) -> list[str]:
            result = await client.list_tools()
            output: list[str] = []
            for item in list(getattr(result, "tools", []) or []):
                try:
                    output.append(normalize_mcp_tool_name(getattr(item, "name", "")))
                except ValueError:
                    continue
            return output

        return list(asyncio.run(self._with_client(config, operation)))

    def call_tool(self, config: MCPServerConfig, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async def operation(client: Any) -> dict[str, Any]:
            result = await client.call_tool(tool, arguments)
            structured = getattr(result, "structured_content", None)
            if structured is None:
                structured = getattr(result, "structuredContent", None)
            content_items: list[Any] = []
            for item in list(getattr(result, "content", []) or [])[:32]:
                if hasattr(item, "model_dump"):
                    try:
                        content_items.append(item.model_dump(mode="json"))
                        continue
                    except Exception:
                        pass
                text = getattr(item, "text", None)
                if text is not None:
                    content_items.append({"type": "text", "text": str(text)})
                else:
                    content_items.append(str(item))
            return {
                "tool": tool,
                "structured_content": structured,
                "content": content_items,
                "is_error": bool(getattr(result, "is_error", getattr(result, "isError", False))),
            }

        return dict(asyncio.run(self._with_client(config, operation)))


class MCPFabric:
    """Node-local bounded MCP discovery and execution coordinator."""

    def __init__(
        self,
        permissions: Any,
        *,
        transport_factory: Callable[[MCPServerConfig], MCPTransport] | None = None,
    ) -> None:
        self.permissions = permissions
        self._transport_factory = transport_factory or (lambda _config: _SDKMCPTransport())
        self._last_error: dict[str, str] = {}
        self._last_discovery: dict[str, list[str]] = {}

    def configured_servers(self) -> dict[str, MCPServerConfig]:
        output: dict[str, MCPServerConfig] = {}
        for server in MCP_SERVER_CAPABILITIES:
            try:
                config = server_config_from_environment(server)
            except ValueError as exc:
                self._last_error[server] = sanitize_mcp_error(f"{type(exc).__name__}: {exc}")
                continue
            if config is not None:
                output[server] = config
        return output

    def status(self) -> dict[str, Any]:
        dependency = mcp_dependency_available()
        configured = self.configured_servers()
        allowed_map = self.permissions.allowed_mcp_tools() if hasattr(self.permissions, "allowed_mcp_tools") else {}
        servers: dict[str, Any] = {}
        for server, capability in MCP_SERVER_CAPABILITIES.items():
            config = configured.get(server)
            allowed_tools = sorted(set(allowed_map.get(server, [])))
            servers[server] = {
                "capability": capability,
                "configured": config is not None,
                "dependency_available": dependency,
                "endpoint_scope": config.endpoint_scope if config else "unconfigured",
                "endpoint": config.endpoint_summary if config else "",
                "authentication_configured": bool(config and config.headers),
                "allowed_tool_count": len(allowed_tools),
                "allowed_tools": allowed_tools,
                "discovered_tool_count": len(self._last_discovery.get(server, [])),
                "last_error": sanitize_mcp_error(self._last_error.get(server, "")),
            }
        return {
            "version": "13.4",
            "transport": "streamable_http",
            "sdk_optional": True,
            "dependency_available": dependency,
            "servers": servers,
            "policy": "configured endpoint + capability permission + exact tool allowlist required; no stdio/shell launcher",
        }

    def capability_descriptors(self) -> list[CapabilityDescriptor]:
        dependency = mcp_dependency_available()
        allowed_map = self.permissions.allowed_mcp_tools() if hasattr(self.permissions, "allowed_mcp_tools") else {}
        output: list[CapabilityDescriptor] = []
        for server, config in self.configured_servers().items():
            allowed_count = len(set(allowed_map.get(server, [])))
            output.append(
                CapabilityDescriptor(
                    name=config.capability,
                    available=dependency,
                    private=config.endpoint_scope == "loopback",
                    local=True,
                    cost="external_policy" if config.endpoint_scope == "remote" else "local",
                    latency="interactive",
                    readiness="degraded" if dependency else "unavailable",
                    metadata={
                        "server": server,
                        "transport": "streamable_http",
                        "endpoint_scope": config.endpoint_scope,
                        "authentication_configured": bool(config.headers),
                        "allowed_tool_count": allowed_count,
                        "discovery": "lazy",
                    },
                )
            )
        return output

    def discover(self, server: str) -> dict[str, Any]:
        normalized = _normalized_server(server)
        config = self.configured_servers().get(normalized)
        if config is None:
            raise RuntimeError(f"MCP server is not configured on this node: {normalized}")
        try:
            tools = self._transport_factory(config).list_tools(config)
            safe_tools = sorted({normalize_mcp_tool_name(item) for item in tools})[:256]
            self._last_discovery[normalized] = safe_tools
            self._last_error.pop(normalized, None)
            return {
                "server": normalized,
                "capability": config.capability,
                "tool_count": len(safe_tools),
                "tools": [
                    {
                        "name": tool,
                        "allowed": bool(self.permissions.is_mcp_tool_allowed(normalized, tool)),
                    }
                    for tool in safe_tools
                ],
                "endpoint_scope": config.endpoint_scope,
            }
        except Exception as exc:
            self._last_error[normalized] = sanitize_mcp_error(f"{type(exc).__name__}: {exc}")
            raise

    def diagnostics(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for server in self.configured_servers():
            try:
                results[server] = {"ok": True, "discovery": self.discover(server)}
            except Exception as exc:
                results[server] = {
                    "ok": False,
                    "error": sanitize_mcp_error(f"{type(exc).__name__}: {exc}"),
                }
        payload = self.status()
        payload["diagnostics"] = results
        return payload

    def execute(self, capability: str, *, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        normalized_capability = str(capability or "").strip().lower()
        server = MCP_CAPABILITY_SERVERS.get(normalized_capability)
        if server is None:
            raise ValueError(f"Unsupported MCP capability: {normalized_capability}")
        clean_tool = normalize_mcp_tool_name(tool)
        if not self.permissions.is_allowed(normalized_capability):
            raise PermissionError(f"Local device permission does not allow {normalized_capability}.")
        if not self.permissions.is_mcp_tool_allowed(server, clean_tool):
            raise PermissionError(f"Local MCP tool permission does not allow {server}/{clean_tool}.")
        config = self.configured_servers().get(server)
        if config is None:
            raise RuntimeError(f"MCP server is not configured on this node: {server}")
        safe_args = sanitize_mcp_task_args(normalized_capability, {"tool": clean_tool, "arguments": arguments})
        try:
            raw = self._transport_factory(config).call_tool(config, clean_tool, dict(safe_args["arguments"]))
            self._last_error.pop(server, None)
        except Exception as exc:
            self._last_error[server] = sanitize_mcp_error(f"{type(exc).__name__}: {exc}")
            raise
        payload = dict(raw or {})
        payload["tool"] = clean_tool
        return sanitize_mcp_result(normalized_capability, payload)
