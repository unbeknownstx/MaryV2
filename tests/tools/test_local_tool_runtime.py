from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.tools.manager import ToolManager


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.provider = "test"
        self.model = "fake-model"
        self.finish_reason = "stop"
        self.usage = {}


class FakeRouter:
    def generate(self, messages, provider=None, temperature=None, max_tokens=None):
        if any(
            "Evaluate Mary's proposed response." in message.content
            for message in messages
        ):
            return FakeLLMResponse(
                "DECISION: ACCEPT\nCONFIDENCE: 0.95\n"
                "ASSESSMENT: grounded\nISSUES: NONE\nSUGGESTIONS: NONE"
            )
        return FakeLLMResponse("I inspected the requested local information.")

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake-model"

    def is_available(self, provider=None):
        return True


def configure_mary(tmp_path) -> Mary:
    mary = Mary()
    fake = FakeRouter()
    mary.llm = fake
    mary.reasoning.llm = fake
    mary.reflection.llm = fake
    mary.tools = ToolManager(workspace_root=tmp_path)
    return mary


def test_detector_maps_local_read_list_search_and_mutation():
    mary = Mary()

    read_intent = mary.cognition.detect_intent("read mary/core/mary.py")
    assert read_intent.intent_type == IntentType.TOOL_USE
    assert read_intent.parameters["tool_name"] == "code_read"
    assert read_intent.parameters["arguments"]["path"] == "mary/core/mary.py"

    list_intent = mary.cognition.detect_intent("show me what's in mary/memory")
    assert list_intent.intent_type == IntentType.TOOL_USE
    assert list_intent.parameters["tool_name"] == "filesystem_list"

    search_intent = mary.cognition.detect_intent("find where MemoryManager is used")
    assert search_intent.intent_type == IntentType.TOOL_USE
    assert search_intent.parameters["tool_name"] == "filesystem_search"
    assert search_intent.parameters["arguments"]["query"] == "MemoryManager"

    write_intent = mary.cognition.detect_intent(
        "create file notes.txt with hello Mary"
    )
    assert write_intent.intent_type == IntentType.TOOL_USE
    assert write_intent.parameters["tool_name"] == "filesystem_write"


def test_safe_local_read_runs_without_approval_and_enters_context(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("class Example:\n    pass\n", encoding="utf-8")

    mary = configure_mary(tmp_path)
    result = mary.process("read example.py")

    assert result.intent is not None
    assert result.intent.intent_type == IntentType.TOOL_USE
    assert result.context.relevant_knowledge

    item = result.context.relevant_knowledge[0]
    assert item["local_tool"] is True
    assert item["tool_name"] == "code_read"
    assert "class Example" in item["content"]
    assert mary.tools.pending_requests() == []


def test_static_code_analysis_does_not_execute_source(tmp_path):
    marker = tmp_path / "executed.txt"
    source = tmp_path / "sample.py"
    source.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('bad')\n"
        "class Sample:\n"
        "    pass\n",
        encoding="utf-8",
    )

    mary = configure_mary(tmp_path)
    result = mary.process("analyze sample.py")

    assert marker.exists() is False
    item = result.context.relevant_knowledge[0]
    assert item["tool_name"] == "code_analyze"
    assert '"Sample"' in item["content"]


def test_workspace_search_is_bounded_and_read_only(tmp_path):
    package = tmp_path / "mary" / "memory"
    package.mkdir(parents=True)
    (package / "manager.py").write_text(
        "class MemoryManager:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "consumer.py").write_text(
        "from mary.memory.manager import MemoryManager\n",
        encoding="utf-8",
    )

    manager = ToolManager(workspace_root=tmp_path)
    result = manager.registry.execute_validated(
        "filesystem_search",
        {
            "query": "MemoryManager",
            "path": ".",
            "max_matches": 20,
        },
    )

    assert result.success is True
    paths = [match.path for match in result.result]
    assert "mary/memory/manager.py" in paths
    assert "consumer.py" in paths
    assert manager.pending_requests() == []


def test_workspace_boundary_blocks_escape(tmp_path):
    manager = ToolManager(workspace_root=tmp_path)
    result = manager.registry.execute_validated(
        "filesystem_read",
        {"path": "../outside.txt"},
    )

    assert result.success is False
    assert "outside Mary's configured filesystem workspace" in result.error


def test_mutating_tool_requires_second_explicit_approval(tmp_path):
    mary = configure_mary(tmp_path)
    target = tmp_path / "notes.txt"

    first = mary.process("create file notes.txt with hello Mary")

    assert target.exists() is False
    assert "would change Mary's workspace" in first.final_response
    pending = mary.tools.pending_requests()
    assert len(pending) == 1
    request = pending[0]
    assert request.tool_name == "filesystem_write"

    second = mary.process(f"approve {request.request_id}")

    assert target.read_text(encoding="utf-8") == "hello Mary"
    assert "completed" in second.final_response
    assert mary.tools.pending_requests() == []


def test_delete_request_does_not_delete_before_approval(tmp_path):
    target = tmp_path / "keep.txt"
    target.write_text("keep", encoding="utf-8")
    mary = configure_mary(tmp_path)

    result = mary.process("delete file keep.txt")

    assert target.exists() is True
    assert "approve request_" in result.final_response
