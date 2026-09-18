from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mary.desktop import device_node as device_module
from mary.distributed import (
    CapabilityDescriptor,
    execute_knowledge_search,
    knowledge_capability_descriptors,
    node_knowledge_fabric,
)


class _Permissions:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    def is_allowed(self, capability: str) -> bool:
        return self._allowed and capability == "knowledge.search"

    def allowed(self):
        return {"knowledge.search"} if self._allowed else set()

    def is_mcp_tool_allowed(self, capability: str, tool: str) -> bool:
        return False


class _MCP:
    def status(self):
        return {}

    def execute(self, *args, **kwargs):
        raise AssertionError("MCP must not execute for knowledge.search")


class _Gateway:
    device_id = "knowledge-node-test"

    def __init__(self) -> None:
        self.completions = []

    def complete_capability_task(self, task_id, *, status, result=None, error=""):
        row = {
            "task_id": task_id,
            "status": status,
            "result": dict(result or {}),
            "error": error,
        }
        self.completions.append(row)
        return {"ok": True, **row}


def _seed_local_pack(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / "manual.md").write_text(
        "Nebularouter is the creator-owned local retrieval regression term.",
        encoding="utf-8",
    )
    fabric = node_knowledge_fabric()
    pack = fabric.register(
        pack_id="manuals",
        title="Creator manuals",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        collection="manuals",
        topics=("mary", "manuals"),
        license="creator-owned",
    )
    fabric.index_local_pack(pack.id)


def test_node_knowledge_capability_is_advertised_and_executes_locally(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MARY_KNOWLEDGE_NODE_ROOT", str(tmp_path / "knowledge-node"))
    _seed_local_pack(tmp_path)

    descriptors = knowledge_capability_descriptors(_Permissions(True))
    assert [item.name for item in descriptors] == ["knowledge.search"]
    assert descriptors[0].metadata["execution_authorized"] is True

    result = execute_knowledge_search({
        "query": "nebularouter",
        "limit": 5,
        "retrieval_mode": "lexical",
        "pack_ids": ["manuals"],
    })
    assert result["ok"] is True
    assert result["retrieval_mode"] == "lexical"
    assert result["hits"]
    assert result["hits"][0]["citation_id"].startswith("knowledge:manuals:")
    assert result["hits"][0]["collection"] == "manuals"


def test_headless_node_discovery_includes_knowledge_descriptor(monkeypatch) -> None:
    monkeypatch.setattr(device_module, "headless_local_llm_capabilities", lambda: [])
    monkeypatch.setattr(
        device_module,
        "knowledge_capability_descriptors",
        lambda permissions: [
            CapabilityDescriptor(
                "knowledge.search",
                private=True,
                local=True,
                metadata={"execution_authorized": True},
            )
        ],
    )
    monkeypatch.setattr(
        device_module,
        "engineering_capability_descriptors",
        lambda permissions: [],
    )
    monkeypatch.setattr(
        device_module,
        "MCPFabric",
        lambda permissions: SimpleNamespace(capability_descriptors=lambda: []),
    )

    rows = device_module.headless_node_capabilities(_Permissions(True))
    assert [item.name for item in rows] == ["knowledge.search"]


def test_device_agent_executes_bounded_knowledge_task(monkeypatch) -> None:
    gateway = _Gateway()
    agent = device_module.DesktopCapabilityNodeAgent(
        gateway,
        capabilities=[
            CapabilityDescriptor(
                "knowledge.search",
                private=True,
                local=True,
            )
        ],
        permissions=_Permissions(True),
        mcp_fabric=_MCP(),
    )
    monkeypatch.setattr(
        device_module,
        "execute_knowledge_search",
        lambda args: {
            "ok": True,
            "hits": [{
                "pack_id": "manuals",
                "title": "Manual",
                "snippet": "bounded",
                "source": "Creator manuals / local_files",
                "score": 1.0,
                "locator": "manual.md",
                "content_hash": "abc",
                "collection": "manuals",
                "source_date": "",
                "indexed_at": "",
                "citation_id": "knowledge:manuals:abc",
            }],
            "pack_count": 1,
            "retrieval_mode": "lexical",
        },
    )

    result = agent._handle_task({
        "task_id": "task-knowledge-1",
        "capability": "knowledge.search",
        "args": {"query": "bounded", "limit": 4},
    })
    assert result["status"] == "completed"
    assert gateway.completions[-1]["result"]["hits"][0]["pack_id"] == "manuals"
    assert agent.status()["last_task"]["status"] == "completed"
