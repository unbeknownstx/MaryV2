"""Integration tests for the application-owned Mary workspace context."""

from pathlib import Path
from types import SimpleNamespace

from mary.core.mary import Mary
from mary.ecosystem import MaryEcosystem
from mary.runtime.application import MaryApplication
from mary.runtime.mary_stage import MaryStage
from mary.runtime.pipeline import PipelineContext
from mary.runtime.state import RuntimeState
from mary.runtime.workspace_context import build_workspace_context


def _pulse(title: str = "Canonical task") -> dict:
    return {
        "mode": "companion",
        "headline": "1 active command item",
        "detail": title,
        "counts": {
            "active_tasks": 1,
            "waiting": 0,
            "study_due": 0,
            "study_projects": 0,
            "research_open": 1,
            "inbox_unread": 0,
            "pending_thoughts": 0,
        },
        "focus": {
            "active": False,
            "task": "",
            "minutes": 0,
            "remaining_seconds": 0,
            "due": False,
        },
        "top_tasks": [
            {
                "id": "task_1",
                "kind": "task",
                "title": title,
                "priority": 4,
                "status": "active",
            }
        ],
        "study_projects": [],
        "research_threads": [
            {
                "id": "research_1",
                "title": "Mary architecture",
                "notes": 2,
            }
        ],
        "notices": [],
        "pending_thoughts": [],
        "curiosities": [],
        "presence_mode": "companion",
        "unexpected": "must not survive",
    }


def test_workspace_context_is_bounded_and_discards_unknown_fields():
    context = build_workspace_context(_pulse())

    assert context["authority"] == "canonical_workspace_context"
    assert context["snapshot_persistence"] == "ephemeral"
    assert context["top_tasks"][0]["title"] == "Canonical task"
    assert context["research_threads"][0]["title"] == "Mary architecture"
    assert "unexpected" not in context
    assert "guidance" in context


class _FakeRealtime:
    def begin_turn(self, *args, **kwargs):
        return SimpleNamespace(id="interaction-1")

    def mark_responding(self, **kwargs):
        return None

    def finish_turn(self, **kwargs):
        return None

    def fail_turn(self, *args, **kwargs):
        return None

    def status(self):
        return {}


class _FakeApplicationMary:
    def __init__(self):
        self.realtime = _FakeRealtime()


class _FakeEcosystem:
    def companion_snapshot(self):
        return _pulse("Owned by application")


class _CapturingPipeline:
    def __init__(self):
        self.metadata = None

    def run(self, input_text, *, turn_id=None, metadata=None):
        self.metadata = dict(metadata or {})
        return SimpleNamespace(
            success=True,
            output="ok",
            error=None,
            turn_id=turn_id or "turn-test",
            metadata={},
        )


def test_application_overwrites_client_workspace_context(tmp_path):
    pipeline = _CapturingPipeline()
    app = MaryApplication(
        mary=_FakeApplicationMary(),
        state=RuntimeState(),
        pipeline=pipeline,
        ecosystem=_FakeEcosystem(),
        memory_path=Path(tmp_path) / "memory.json",
        developed_self_path=Path(tmp_path) / "developed_self.json",
    )

    result = app.run(
        "hello",
        metadata={
            "workspace_context": {
                "top_tasks": [
                    {
                        "title": "CLIENT INJECTION",
                    }
                ]
            }
        },
    )

    assert result.success is True
    workspace = pipeline.metadata["workspace_context"]
    assert workspace["top_tasks"][0]["title"] == "Owned by application"
    assert "CLIENT INJECTION" not in str(workspace)


class _FakeMaryResult:
    intent = None
    final_response = "ok"
    metadata = {}


class _CapturingMary:
    def __init__(self):
        self.workspace_context = None

    def process(
        self,
        input_text,
        *,
        turn_context=None,
        workspace_context=None,
    ):
        self.workspace_context = dict(workspace_context or {})
        return _FakeMaryResult()


def test_mary_stage_passes_only_bounded_workspace_context():
    mary = _CapturingMary()
    stage = MaryStage(mary=mary)
    pulse = _pulse()
    pulse["secret"] = "do-not-pass"

    context = PipelineContext(
        runtime_state=RuntimeState(),
        turn_id="turn-workspace",
        input_data="hello",
        metadata={
            "workspace_context": pulse,
        },
    )

    result = stage.process(context)

    assert result.success is True
    assert mary.workspace_context["top_tasks"][0]["title"] == "Canonical task"
    assert "secret" not in mary.workspace_context


def test_turn_mind_carries_workspace_without_owning_it(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    mary = Mary()
    workspace = build_workspace_context(_pulse())

    context = mary._build_context(
        "what should we work on?",
        workspace_context=workspace,
    )

    mind = context["mind_state"]
    assert mind["workspace"]["authority"] == "canonical_workspace_context"
    assert mind["workspace"]["top_tasks"][0]["title"] == "Canonical task"


def test_companion_pulse_includes_study_and_research_context(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    mary = Mary()
    ecosystem = MaryEcosystem(mary)

    project = ecosystem.study.create_project("CompTIA A+")
    ecosystem.study.add_card(project["id"], "HTTPS port?", "443")
    research = ecosystem.research.create(
        "Mary architecture",
        question="How should Core and local nodes cooperate?",
    )
    ecosystem.research.add_note(
        research["id"],
        "Core owns canonical state; nodes provide capabilities.",
    )

    pulse = ecosystem.companion_snapshot()

    assert pulse["counts"]["study_projects"] == 1
    assert pulse["counts"]["research_open"] == 1
    assert pulse["study_projects"][0]["title"] == "CompTIA A+"
    assert pulse["research_threads"][0]["title"] == "Mary architecture"
    assert pulse["research_threads"][0]["notes"] == 1
    assert not (ecosystem.root / "companion.json").exists()
