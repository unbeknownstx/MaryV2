import json

import pytest

from mary.distributed import DeviceExecutionPermissions


def test_mcp_tool_permissions_are_independent_from_capability_gate(tmp_path):
    path = tmp_path / "permissions.json"
    permissions = DeviceExecutionPermissions(path)

    permissions.allow_mcp_tool("opendesign", "recommend_references")
    assert permissions.is_mcp_tool_allowed("opendesign", "recommend_references")
    assert not permissions.is_allowed("mcp.opendesign")

    permissions.allow("mcp.opendesign")
    assert permissions.is_allowed("mcp.opendesign")
    assert permissions.is_mcp_tool_allowed("mcp.opendesign", "recommend_references")

    permissions.deny_mcp_tool("mcp.opendesign", "recommend_references")
    assert not permissions.is_mcp_tool_allowed("opendesign", "recommend_references")
    assert permissions.is_allowed("mcp.opendesign")


def test_old_permission_file_remains_compatible(tmp_path):
    path = tmp_path / "permissions.json"
    path.write_text(
        json.dumps(
            {
                "version": "13.3",
                "allowed_capabilities": ["llm.ollama", "unknown.capability"],
            }
        ),
        encoding="utf-8",
    )
    permissions = DeviceExecutionPermissions(path)

    assert permissions.allowed() == {"llm.ollama"}
    assert permissions.allowed_mcp_tools() == {}


def test_permission_file_writes_only_bounded_capability_and_tool_names(tmp_path):
    path = tmp_path / "permissions.json"
    permissions = DeviceExecutionPermissions(path)
    permissions.allow("mcp.langflow")
    permissions.allow_mcp_tool("langflow", "project_flow-1")

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == "13.4"
    assert raw["allowed_capabilities"] == ["mcp.langflow"]
    assert raw["allowed_mcp_tools"] == {"langflow": ["project_flow-1"]}
    assert "shell" not in repr(raw).lower()

    with pytest.raises(ValueError):
        permissions.allow("shell")
    with pytest.raises(ValueError):
        permissions.allow_mcp_tool("unknown", "anything")
    with pytest.raises(ValueError):
        permissions.allow_mcp_tool("langflow", "bad tool name")
