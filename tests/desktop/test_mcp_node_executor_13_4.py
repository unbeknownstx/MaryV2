from mary.desktop.device_node import DesktopCapabilityNodeAgent
from mary.distributed import CapabilityDescriptor, DeviceExecutionPermissions


class _Gateway:
    device_id = "mcp-node"

    def __init__(self):
        self.completions = []

    def complete_capability_task(self, task_id, *, status, result=None, error=""):
        payload = {
            "task_id": task_id,
            "status": status,
            "result": result or {},
            "error": error,
        }
        self.completions.append(payload)
        return {"ok": True, "task": payload}


class _FakeFabric:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"version": "test"}

    def execute(self, capability, *, tool, arguments):
        self.calls.append((capability, tool, dict(arguments)))
        return {
            "server": "opendesign",
            "tool": tool,
            "structured_content": {"result": "ok"},
            "privacy": "sanitized",
        }


def _task():
    return {
        "task_id": "capability_task_test",
        "capability": "mcp.opendesign",
        "args": {
            "tool": "recommend_references",
            "arguments": {"query": "companion UI"},
        },
    }


def test_device_agent_requires_capability_and_tool_permission(tmp_path):
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    gateway = _Gateway()
    fabric = _FakeFabric()
    agent = DesktopCapabilityNodeAgent(
        gateway,
        capabilities=[
            CapabilityDescriptor(
                name="mcp.opendesign",
                available=True,
                private=False,
                local=True,
                readiness="ready",
            )
        ],
        host_type="capability_node",
        surface="capability_node",
        permissions=permissions,
        mcp_fabric=fabric,
    )

    first = agent._handle_task(_task())
    assert first["task"]["status"] == "rejected"
    assert "Local device permission" in first["task"]["error"]
    assert fabric.calls == []

    permissions.allow("mcp.opendesign")
    second = agent._handle_task(_task())
    assert second["task"]["status"] == "rejected"
    assert "Local MCP tool permission" in second["task"]["error"]
    assert fabric.calls == []

    permissions.allow_mcp_tool("opendesign", "recommend_references")
    third = agent._handle_task(_task())
    assert third["task"]["status"] == "completed"
    assert third["task"]["result"]["structured_content"] == {"result": "ok"}
    assert fabric.calls == [
        (
            "mcp.opendesign",
            "recommend_references",
            {"query": "companion UI"},
        )
    ]
