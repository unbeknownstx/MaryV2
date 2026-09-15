from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mary.orchestration.evidence_selection import select_prompt_evidence
from mary.orchestration.execution import OrchestrationExecutor
from mary.orchestration.models import TaskEvidence


def _evidence(evidence_id, content, provenance, *, age_seconds=0, confidence=0.5):
    item = TaskEvidence(
        evidence_id=evidence_id,
        content=content,
        provenance=provenance,
        confidence=confidence,
    )
    object.__setattr__(
        item,
        "created_at",
        (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat(),
    )
    return item


def test_old_rebuildable_tool_output_ages_out_but_creator_evidence_does_not():
    rows = [
        _evidence("tool-old", "large old tool output", "local_tool", age_seconds=7200, confidence=0.7),
        _evidence("creator-old", "creator constraint", "creator", age_seconds=86400, confidence=0.6),
        _evidence("tool-new", "fresh tool output", "local_tool", age_seconds=30, confidence=0.7),
    ]
    selection = select_prompt_evidence(rows, rebuildable_ttl_seconds=1800)
    ids = [item.evidence_id for item in selection.selected]
    assert "tool-old" not in ids
    assert "creator-old" in ids
    assert "tool-new" in ids
    assert "tool-old" in selection.stale_ids


def test_high_importance_old_rebuildable_evidence_can_survive_ttl():
    row = _evidence("verify-old", "important result", "test_result", age_seconds=7200, confidence=1.0)
    selection = select_prompt_evidence([row], rebuildable_ttl_seconds=1800)
    assert [item.evidence_id for item in selection.selected] == ["verify-old"]


def test_selector_never_mutates_workspace_evidence_collection():
    rows = [
        _evidence("old", "old", "local_tool", age_seconds=7200),
        _evidence("new", "new", "local_tool", age_seconds=10),
    ]
    before = list(rows)
    select_prompt_evidence(rows, rebuildable_ttl_seconds=1800)
    assert rows == before
    assert len(rows) == 2


def test_executor_generation_prompt_uses_selector_and_exposes_content_free_telemetry():
    old = _evidence("old-tool", "SHOULD NOT ENTER PROMPT", "local_tool", age_seconds=7200)
    creator = _evidence("creator", "KEEP THIS CONSTRAINT", "creator", age_seconds=7200)
    task = SimpleNamespace(objective="Do the task", evidence=[old, creator])
    executor = object.__new__(OrchestrationExecutor)
    executor.router = SimpleNamespace(
        config=SimpleNamespace(
            governance=SimpleNamespace(task_text_characters=4000)
        )
    )
    executor._last_prompt_evidence = {}

    prompt = executor._generation_prompt(task, prompt=None)
    assert "SHOULD NOT ENTER PROMPT" not in prompt
    assert "KEEP THIS CONSTRAINT" in prompt
    telemetry = executor._last_prompt_evidence
    assert telemetry["policy_version"] == "13.46"
    assert "old-tool" in telemetry["stale_ids"]
    assert "SHOULD NOT ENTER PROMPT" not in str(telemetry)
    assert "KEEP THIS CONSTRAINT" not in str(telemetry)


def test_redacted_only_prompt_does_not_reintroduce_workspace_evidence():
    task = SimpleNamespace(
        objective="secret task",
        evidence=[_evidence("creator", "private creator fact", "creator")],
    )
    executor = object.__new__(OrchestrationExecutor)
    executor.router = SimpleNamespace(
        config=SimpleNamespace(
            governance=SimpleNamespace(task_text_characters=4000)
        )
    )
    executor._last_prompt_evidence = {}
    prompt = executor._generation_prompt(task, prompt="safe redacted request", redacted_only=True)
    assert "safe redacted request" in prompt
    assert "private creator fact" not in prompt
    assert executor._last_prompt_evidence["selected_count"] == 0
