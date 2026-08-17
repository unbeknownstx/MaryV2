from __future__ import annotations

import json

from mary.cognition.code_change import CodeChangePlanner
from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse
from mary.tools.manager import ToolManager


class PlannerRouter:
    def __init__(self, old_text: str, new_text: str) -> None:
        self.old_text = old_text
        self.new_text = new_text
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        prompt = messages[-1].content

        if "CODE CHANGE PLANNER" in prompt:
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Update the greeting return value.",
                        "edits": [
                            {
                                "old_text": self.old_text,
                                "new_text": self.new_text,
                            }
                        ],
                    }
                ),
                provider="test",
                model="planner",
            )

        return LLMResponse(
            content="DECISION: ACCEPT\nCONFIDENCE: 1.0\nASSESSMENT: ok",
            provider="test",
            model="planner",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "planner"

    def is_available(self, provider=None):
        return True


class InvalidPlannerRouter(PlannerRouter):
    def generate(self, messages, **kwargs):
        prompt = messages[-1].content
        self.calls.append((messages, kwargs))

        if "CODE CHANGE PLANNER" in prompt:
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Break syntax",
                        "edits": [
                            {
                                "old_text": self.old_text,
                                "new_text": "def greet(:\n    return 'broken'\n",
                            }
                        ],
                    }
                ),
                provider="test",
                model="planner",
            )

        return super().generate(messages, **kwargs)


def configure_mary(tmp_path, router) -> Mary:
    mary = Mary()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.tools = ToolManager(workspace_root=tmp_path)
    mary.code_change_planner = CodeChangePlanner(
        llm=router,
        code=mary.tools.code,
    )
    return mary


def test_direct_file_open_warning_is_not_reported(tmp_path):
    path = tmp_path / "context_file.py"
    path.write_text(
        "from pathlib import Path\n\n"
        "def read_it(path: Path):\n"
        "    with path.open('r', encoding='utf-8') as file:\n"
        "        return file.read()\n",
        encoding="utf-8",
    )

    manager = ToolManager(workspace_root=tmp_path)
    result = manager.registry.execute_validated(
        "code_analyze",
        {"path": "context_file.py"},
    )

    assert result.success is True
    assert "Uses direct file opening." not in result.result.warnings


def test_planner_creates_diff_without_modifying_file(tmp_path):
    source = "def greet():\n    return 'old'\n"
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")

    router = PlannerRouter(
        "def greet():\n    return 'old'\n",
        "def greet():\n    return 'hello'\n",
    )
    manager = ToolManager(workspace_root=tmp_path)
    planner = CodeChangePlanner(llm=router, code=manager.code)

    plan = planner.propose(
        "sample.py",
        "make greet return hello",
    )

    assert path.read_text(encoding="utf-8") == source
    assert plan.validation["valid"] is True
    assert "-    return 'old'" in plan.change.diff
    assert "+    return 'hello'" in plan.change.diff
    assert plan.change.metadata["original_sha256"]
    assert plan.metadata["file_modified"] is False


def test_invalid_python_proposal_is_rejected_before_approval(tmp_path):
    source = "def greet():\n    return 'old'\n"
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")

    router = InvalidPlannerRouter(
        "def greet():\n    return 'old'\n",
        "unused",
    )
    manager = ToolManager(workspace_root=tmp_path)
    planner = CodeChangePlanner(llm=router, code=manager.code)

    try:
        planner.propose("sample.py", "break it")
    except ValueError as exc:
        assert "failed static validation" in str(exc)
    else:
        raise AssertionError("invalid proposal should have been rejected")

    assert path.read_text(encoding="utf-8") == source
    assert manager.pending_requests() == []


def test_stale_approved_change_cannot_overwrite_newer_source(tmp_path):
    source = "def greet():\n    return 'old'\n"
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")

    manager = ToolManager(workspace_root=tmp_path)
    change = manager.code.propose_change(
        "sample.py",
        "def greet():\n    return 'hello'\n",
        reason="test",
    )
    request = manager.request(
        "code_apply_change",
        {"change": change.to_dict()},
        reason="test",
    )

    # Simulate another editor changing the file before creator approval.
    path.write_text(
        "def greet():\n    return 'newer manual edit'\n",
        encoding="utf-8",
    )

    assert manager.approve(request.request_id) is not None
    result = manager.execute_approved(request.request_id)

    assert result.success is False
    assert "Source changed after the proposal was created" in result.error
    assert "newer manual edit" in path.read_text(encoding="utf-8")


def test_mary_proposes_then_applies_only_after_second_approval(tmp_path):
    source = "def greet():\n    return 'old'\n"
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")

    router = PlannerRouter(
        "def greet():\n    return 'old'\n",
        "def greet():\n    return 'hello'\n",
    )
    mary = configure_mary(tmp_path, router)

    intent = mary.cognition.detect_intent(
        "change sample.py so greet returns hello"
    )
    assert intent.intent_type == IntentType.TOOL_USE
    assert intent.parameters["action"] == "propose_code_change"

    first = mary.process(
        "change sample.py so greet returns hello"
    )

    assert path.read_text(encoding="utf-8") == source
    assert "Nothing has been written or executed." in first.final_response
    assert "```diff" in first.final_response
    assert "approve request_" in first.final_response
    assert first.metadata["llm_calls_after_planning"] == 0

    pending = mary.tools.pending_requests()
    assert len(pending) == 1
    request = pending[0]
    assert request.tool_name == "code_apply_change"

    second = mary.process(
        f"approve {request.request_id}"
    )

    assert "return 'hello'" in path.read_text(encoding="utf-8")
    assert "No code or tests were executed." in second.final_response


def test_large_file_planner_uses_grounded_windows(tmp_path):
    filler = "\n".join(
        f"value_{index} = {index}"
        for index in range(1800)
    )
    target = (
        "\n\nclass TargetThing:\n"
        "    def important_method(self):\n"
        "        return 'old-value'\n"
    )
    source = filler + target
    path = tmp_path / "large.py"
    path.write_text(source, encoding="utf-8")

    router = PlannerRouter(
        "    def important_method(self):\n        return 'old-value'\n",
        "    def important_method(self):\n        return 'new-value'\n",
    )
    manager = ToolManager(workspace_root=tmp_path)
    planner = CodeChangePlanner(llm=router, code=manager.code)

    plan = planner.propose(
        "large.py",
        "change TargetThing important_method to return new-value",
    )

    assert plan.change.metadata["planning_source_complete"] is False
    assert plan.change.metadata["planning_source_characters"] <= planner.MAX_SOURCE_CHARS
    prompt = router.calls[0][0][-1].content
    assert "important_method" in prompt
    assert "SOURCE COMPLETE: False" in prompt
    assert "new-value" in plan.change.proposed
