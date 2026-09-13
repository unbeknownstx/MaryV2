from pathlib import Path

from mary.tools.manager import ToolManager
from mary.tools.registry import PermissionLevel


def test_knowledge_search_is_registered_and_approval_required(tmp_path: Path):
    manager = ToolManager(workspace_root=tmp_path)
    definition = manager.registry.get("knowledge_search")
    assert definition is not None
    assert definition.permission_level == PermissionLevel.APPROVAL_REQUIRED
    assert definition.external_access is True
    assert definition.mutates_state is False


def test_knowledge_gateway_registration_does_not_touch_network(tmp_path: Path):
    manager = ToolManager(workspace_root=tmp_path)
    status = manager.status()["knowledge_gateway"]
    assert status["startup_network_dependency"] is False
    assert status["authority"] == "external_evidence_only"
