from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from mary.ecosystem import MaryEcosystem
from mary.productivity import CommandCenter
from mary.protocol.models import WorkspaceActionRequest


class _Attention:
    def publish(self, *args, **kwargs):
        return None

    def snapshot(self):
        return {"pending": 0}


class _Realtime:
    def __init__(self):
        self.attention = _Attention()

    def status(self):
        return {"phase": "idle"}


class _Curiosities:
    def get_exploring_curiosities(self):
        return []

    def get_open_curiosities(self):
        return []


class _Mary:
    def __init__(self, tmp_path):
        self.config = SimpleNamespace(
            paths=SimpleNamespace(
                data=tmp_path,
                workspace=tmp_path / "workspace",
                root=tmp_path,
                models=tmp_path / "models",
            )
        )
        self.realtime = _Realtime()
        self.agency = SimpleNamespace(curiosities=_Curiosities())


def test_command_center_project_task_link_survives_restart(tmp_path):
    root = tmp_path / "ecosystem"
    first = CommandCenter(root)

    project = first.create_project(
        "Cleaning Business",
        priority=4,
        notes="Commercial cleaning sales and operations.",
    )
    task = first.create_task(
        "Follow up with ABC Property Management",
        project_id=project["id"],
        priority=3,
        due_at="2026-09-18T09:00:00-07:00",
    )

    assert task["project_id"] == project["id"]
    assert task["project_title"] == "Cleaning Business"
    assert first.summary()["projects"] == 1
    assert first.summary()["active_tasks"] == 1

    restarted = CommandCenter(root)
    reloaded = restarted.list_tasks(project_id=project["id"])

    assert len(reloaded) == 1
    assert reloaded[0]["id"] == task["id"]
    assert reloaded[0]["project_title"] == "Cleaning Business"
    assert reloaded[0]["due_at"] == "2026-09-18T09:00:00-07:00"


def test_command_center_completion_survives_restart(tmp_path):
    root = tmp_path / "ecosystem"
    first = CommandCenter(root)
    project = first.create_project("MaryV2")
    task = first.create_task("Verify Windows node", project_id=project["id"])

    completed = first.complete_task(task["id"])

    assert completed["status"] == "done"
    assert completed["completed_at"]
    assert first.summary()["active_tasks"] == 0
    assert first.summary()["completed_tasks"] == 1

    restarted = CommandCenter(root)
    reloaded = restarted.get(task["id"])
    assert reloaded is not None
    assert reloaded["status"] == "done"
    assert reloaded["completed_at"] == completed["completed_at"]


def test_command_center_rejects_dangling_project_links(tmp_path):
    command = CommandCenter(tmp_path / "ecosystem")

    with pytest.raises(KeyError):
        command.create_task(
            "Orphan task",
            project_id="project_missing",
        )


def test_command_center_loads_v1_records_with_v2_defaults(tmp_path):
    root = tmp_path / "ecosystem"
    root.mkdir(parents=True)
    (root / "command_center.json").write_text(
        json.dumps(
            {
                "version": 1,
                "items": [
                    {
                        "id": "task_legacy",
                        "kind": "task",
                        "title": "Legacy task",
                        "status": "active",
                        "priority": 2,
                        "notes": "",
                        "created_at": "2026-09-01T00:00:00+00:00",
                        "updated_at": "2026-09-01T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    command = CommandCenter(root)
    legacy = command.get("task_legacy")

    assert legacy is not None
    assert legacy["project_id"] == ""
    assert legacy["due_at"] == ""
    assert legacy["completed_at"] == ""


def test_workspace_protocol_accepts_typed_project_task_actions():
    for action in (
        "project.create",
        "project.update",
        "task.create",
        "task.update",
        "task.complete",
    ):
        request = WorkspaceActionRequest.from_dict(
            {"action": action, "args": {}, "device_id": "iphone"}
        )
        assert request.action == action


def test_ecosystem_project_task_round_trip_is_canonical_and_durable(tmp_path):
    first = MaryEcosystem(_Mary(tmp_path))

    created_project = first.apply_workspace_action(
        "project.create",
        {
            "title": "Cleaning Business",
            "priority": 4,
        },
        source="test_surface_a",
    )
    project = created_project["project"]

    created_task = first.apply_workspace_action(
        "task.create",
        {
            "title": "Prepare janitorial proposal",
            "project_id": project["id"],
            "priority": 4,
            "due_at": "2026-09-20",
        },
        source="test_surface_b",
    )
    task = created_task["task"]

    snapshot = first.workspace_snapshot()
    command = snapshot["command"]
    assert command["projects"] == 1
    assert command["active_tasks"] == 1
    assert task["project_title"] == "Cleaning Business"

    second = MaryEcosystem(_Mary(tmp_path))
    second_snapshot = second.workspace_snapshot()
    reloaded = next(
        item
        for item in second_snapshot["command"]["items"]
        if item["id"] == task["id"]
    )
    assert reloaded["project_id"] == project["id"]
    assert reloaded["project_title"] == "Cleaning Business"

    completed = second.apply_workspace_action(
        "task.complete",
        {"task_id": task["id"]},
        source="test_surface_c",
    )["task"]
    assert completed["status"] == "done"

    third = MaryEcosystem(_Mary(tmp_path))
    final = third.workspace_snapshot()["command"]
    assert final["active_tasks"] == 0
    assert final["completed_tasks"] == 1
