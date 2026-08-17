from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.tools.manager import ToolManager


def _mary_with_temp_tools(tmp_path):
    mary = Mary()
    mary.tools = ToolManager(workspace_root=tmp_path)
    return mary


def test_bare_approve_detects_tool_control():
    mary = Mary()
    intent = mary.cognition.detect_intent("approve")

    assert intent.intent_type == IntentType.TOOL_USE
    assert intent.parameters["action"] == "approve"
    assert intent.parameters["request_id"] == ""
    assert intent.parameters["resolve_single_pending"] is True


def test_approve_request_without_id_detects_tool_control():
    mary = Mary()
    intent = mary.cognition.detect_intent("approve request")

    assert intent.intent_type == IntentType.TOOL_USE
    assert intent.parameters["action"] == "approve"
    assert intent.parameters["request_id"] == ""


def test_bare_approve_executes_only_single_pending_request(tmp_path):
    mary = _mary_with_temp_tools(tmp_path)
    request = mary.tools.request(
        "filesystem_write",
        {
            "path": "approved.txt",
            "content": "approved",
            "overwrite": False,
        },
        reason="test",
    )

    assert request.status == "pending"
    assert not (tmp_path / "approved.txt").exists()

    intent = mary.cognition.detect_intent("approve")
    action = mary._handle_tool_control(intent)

    assert (tmp_path / "approved.txt").read_text(encoding="utf-8") == "approved"
    assert request.status == "executed"
    assert "filesystem_write completed" in action["system_response"]


def test_bare_reject_rejects_only_single_pending_request(tmp_path):
    mary = _mary_with_temp_tools(tmp_path)
    request = mary.tools.request(
        "filesystem_write",
        {
            "path": "rejected.txt",
            "content": "no",
            "overwrite": False,
        },
        reason="test",
    )

    intent = mary.cognition.detect_intent("reject")
    action = mary._handle_tool_control(intent)

    assert request.status == "rejected"
    assert not (tmp_path / "rejected.txt").exists()
    assert "Rejected" in action["system_response"]


def test_bare_approve_never_guesses_between_multiple_requests(tmp_path):
    mary = _mary_with_temp_tools(tmp_path)
    first = mary.tools.request(
        "filesystem_write",
        {"path": "one.txt", "content": "one", "overwrite": False},
        reason="one",
    )
    second = mary.tools.request(
        "filesystem_write",
        {"path": "two.txt", "content": "two", "overwrite": False},
        reason="two",
    )

    intent = mary.cognition.detect_intent("approve")
    action = mary._handle_tool_control(intent)

    assert "More than one tool request is pending" in action["system_response"]
    assert first.request_id in action["system_response"]
    assert second.request_id in action["system_response"]
    assert first.status == "pending"
    assert second.status == "pending"
    assert not (tmp_path / "one.txt").exists()
    assert not (tmp_path / "two.txt").exists()


def test_bare_approve_with_no_pending_request_is_deterministic(tmp_path):
    mary = _mary_with_temp_tools(tmp_path)
    intent = mary.cognition.detect_intent("approve")
    action = mary._handle_tool_control(intent)

    assert action["system_response"] == "There are no pending tool requests to approve."


def test_mutating_request_returns_without_llm_call(tmp_path):
    mary = _mary_with_temp_tools(tmp_path)

    result = mary.process(
        "create file no_llm.txt with pending only"
    )

    assert "filesystem_write would change Mary's workspace" in result.final_response
    assert "you can simply say: approve" in result.final_response
    assert result.metadata["llm_calls_after_action"] == 0
    assert not (tmp_path / "no_llm.txt").exists()
    assert len(mary.tools.pending_requests()) == 1


def test_proposed_dynamic_web_request_returns_without_llm_call(tmp_path):
    mary = _mary_with_temp_tools(tmp_path)

    result = mary.process(
        "what is the latest Python release?"
    )

    assert "Current external information would help answer that" in result.final_response
    assert "you can simply say: approve" in result.final_response
    assert result.metadata["llm_calls_after_action"] == 0
    pending = mary.tools.pending_requests()
    assert len(pending) == 1
    assert pending[0].tool_name == "web_search"
