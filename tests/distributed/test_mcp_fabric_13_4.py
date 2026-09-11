import json

import pytest

from mary.distributed import DeviceExecutionPermissions, MCPFabric
from mary.distributed import mcp_fabric as mcp_module
from mary.distributed.mcp_fabric import (
    sanitize_mcp_result,
    sanitize_mcp_task_args,
    server_config_from_environment,
)


class _FakeTransport:
    def __init__(self):
        self.calls = []

    def list_tools(self, config):
        self.calls.append(("list", config.server))
        return ["recommend_references", "get_design_system"]

    def call_tool(self, config, tool, arguments):
        self.calls.append(("call", config.server, tool, dict(arguments)))
        return {
            "tool": tool,
            "structured_content": {
                "value": "ok",
                "token": "SHOULD-NOT-RETURN",
            },
            "content": [
                {"type": "text", "text": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz"},
            ],
            "headers": {"Authorization": "Bearer ALSO-SECRET"},
            "endpoint": config.url,
        }


def test_mcp_status_is_local_safe_and_does_not_expose_headers(monkeypatch, tmp_path):
    monkeypatch.setenv("MARY_MCP_OPENDESIGN_URL", "https://opendesign.cc/mcp/http")
    monkeypatch.setenv(
        "MARY_MCP_OPENDESIGN_HEADERS_JSON",
        json.dumps({"Authorization": "Bearer TOP-SECRET-VALUE"}),
    )
    monkeypatch.setattr(mcp_module, "mcp_dependency_available", lambda: True)
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    fabric = MCPFabric(permissions, transport_factory=lambda _config: _FakeTransport())

    status = fabric.status()
    rendered = repr(status)
    assert "TOP-SECRET-VALUE" not in rendered
    assert status["servers"]["opendesign"]["configured"] is True
    assert status["servers"]["opendesign"]["authentication_configured"] is True
    assert status["servers"]["opendesign"]["endpoint"] == "https://opendesign.cc"
    assert status["servers"]["opendesign"]["discovered_tool_count"] == 0

    descriptors = fabric.capability_descriptors()
    assert [item.name for item in descriptors] == ["mcp.opendesign"]
    assert descriptors[0].routable is True
    assert "TOP-SECRET-VALUE" not in repr(descriptors[0].to_dict())


def test_mcp_execute_requires_capability_and_exact_tool_allow(monkeypatch, tmp_path):
    monkeypatch.setenv("MARY_MCP_OPENDESIGN_URL", "https://opendesign.cc/mcp/http")
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    transport = _FakeTransport()
    fabric = MCPFabric(permissions, transport_factory=lambda _config: transport)

    with pytest.raises(PermissionError, match="Local device permission"):
        fabric.execute(
            "mcp.opendesign",
            tool="recommend_references",
            arguments={"query": "mobile companion"},
        )

    permissions.allow("mcp.opendesign")
    with pytest.raises(PermissionError, match="Local MCP tool permission"):
        fabric.execute(
            "mcp.opendesign",
            tool="recommend_references",
            arguments={"query": "mobile companion"},
        )

    permissions.allow_mcp_tool("opendesign", "recommend_references")
    result = fabric.execute(
        "mcp.opendesign",
        tool="recommend_references",
        arguments={"query": "mobile companion"},
    )
    rendered = repr(result)
    assert result["server"] == "opendesign"
    assert result["tool"] == "recommend_references"
    assert "SHOULD-NOT-RETURN" not in rendered
    assert "ALSO-SECRET" not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
    assert "opendesign.cc/mcp/http" not in rendered
    assert transport.calls[-1][0] == "call"


def test_mcp_discovery_lists_names_without_granting_permission(monkeypatch, tmp_path):
    monkeypatch.setenv("MARY_MCP_OPENDESIGN_URL", "https://opendesign.cc/mcp/http")
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    permissions.allow_mcp_tool("opendesign", "get_design_system")
    fabric = MCPFabric(permissions, transport_factory=lambda _config: _FakeTransport())

    discovery = fabric.discover("opendesign")
    assert discovery["tool_count"] == 2
    assert discovery["tools"] == [
        {"name": "get_design_system", "allowed": True},
        {"name": "recommend_references", "allowed": False},
    ]
    assert not permissions.is_allowed("mcp.opendesign")


def test_mcp_task_arguments_reject_secret_material():
    with pytest.raises(ValueError, match="secret field"):
        sanitize_mcp_task_args(
            "mcp.scrapling",
            {
                "tool": "make_request",
                "arguments": {
                    "url": "https://example.com",
                    "headers": {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
                },
            },
        )

    with pytest.raises(ValueError, match="credentials or bearer tokens"):
        sanitize_mcp_task_args(
            "mcp.langflow",
            {
                "tool": "example_flow",
                "arguments": {"input": "Bearer abcdefghijklmnopqrstuvwxyz"},
            },
        )


def test_mcp_results_are_bounded_and_secret_sanitized():
    result = sanitize_mcp_result(
        "mcp.langflow",
        {
            "tool": "example_flow",
            "structured_content": {
                "api_key": "super-secret",
                "answer": "safe",
            },
            "url": "https://private.example/path",
            "content": [{"text": "sk-abcdefghijklmnopq"}],
        },
    )
    rendered = repr(result)
    assert result["server"] == "langflow"
    assert result["structured_content"]["api_key"] == "[REDACTED]"
    assert result["structured_content"]["answer"] == "safe"
    assert "private.example" not in rendered
    assert "abcdefghijklmnopq" not in rendered


def test_non_loopback_plain_http_is_fail_closed(monkeypatch):
    monkeypatch.setenv("MARY_MCP_SCRAPLING_URL", "http://scraper.internal:8000/mcp")
    monkeypatch.delenv("MARY_MCP_ALLOW_INSECURE_REMOTE", raising=False)
    with pytest.raises(ValueError, match="plaintext HTTP"):
        server_config_from_environment("scrapling")

    monkeypatch.setenv("MARY_MCP_ALLOW_INSECURE_REMOTE", "true")
    config = server_config_from_environment("scrapling")
    assert config is not None
    assert config.endpoint_scope == "remote"
