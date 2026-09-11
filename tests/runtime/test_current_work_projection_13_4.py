from types import SimpleNamespace

from mary.runtime.current_work import build_current_work_projection
from mary.runtime.workspace_context import build_workspace_context


class _History:
    def get_recent(self, limit=32):
        return [
            {
                "type": "shared_experience",
                "description": "We were working on you on the Mac and now have you an iPhone app",
                "metadata": {"kind": "shared_work", "owner": "creator"},
            },
            {
                "type": "shared_experience",
                "description": "We connected your Mac capability node to Core",
                "metadata": {"kind": "shared_work", "owner": "creator"},
            },
        ]


class _Milestones:
    def get_recent(self, limit=8):
        return []


class _Mary:
    relationship_history = _History()
    relationship_milestones = _Milestones()

    @staticmethod
    def _render_creator_owned_shared_work(text):
        return str(text).replace("working on you", "working on me").replace("your Mac", "my Mac")


def test_current_work_projection_uses_shared_work_when_workspace_is_empty():
    projection = build_current_work_projection(_Mary(), {})

    assert projection["active"] is True
    assert projection["project"] == "MaryV2"
    assert "iPhone app" in projection["summary"]
    assert projection["authority"] == "derived_current_work_projection"
    assert projection["persistence"] == "projection_only"
    assert "relationship.shared_work" in projection["sources"]


def test_active_workspace_item_precedes_historical_shared_work():
    projection = build_current_work_projection(
        _Mary(),
        {
            "focus": {"active": True, "task": "Verify native iPhone voice"},
            "command": {
                "items": [
                    {"title": "Finish 13.4 live acceptance", "status": "active", "kind": "project"}
                ]
            },
            "production": {"recent": []},
        },
    )

    assert projection["summary"] == "Verify native iPhone voice"
    assert projection["stage"] == "active"
    assert projection["recent"][0]["source"] == "workspace.focus"


def test_workspace_context_preserves_only_bounded_current_work_projection():
    context = build_workspace_context(
        {
            "mode": "companion",
            "current_work": {
                "active": True,
                "project": "MaryV2",
                "stage": "13.4 candidate",
                "summary": "Connect native iPhone voice and continuity",
                "recent": [
                    {
                        "summary": "Connect native iPhone voice and continuity",
                        "source": "relationship.shared_work",
                        "kind": "shared_work",
                        "secret": "must not survive",
                    }
                ],
                "secret": "must not survive",
            },
        }
    )

    current = context["current_work"]
    assert current["project"] == "MaryV2"
    assert current["authority"] == "derived_current_work_projection"
    assert "secret" not in str(current)
