from types import SimpleNamespace

from mary.creative import ProductionStudio
from mary.ecosystem import MaryEcosystem
from mary.protocol.models import WorkspaceActionRequest, RuntimeActionRequest


class _Attention:
    def publish(self, *args, **kwargs): return None
    def snapshot(self): return {"pending": 0}


class _Realtime:
    def __init__(self): self.attention = _Attention()


class _Mary:
    def __init__(self, tmp_path):
        self.config = SimpleNamespace(paths=SimpleNamespace(data=tmp_path, workspace=tmp_path / "workspace", root=tmp_path))
        self.realtime = _Realtime()
        self.agency = SimpleNamespace(curiosities=SimpleNamespace(get_exploring_curiosities=lambda: [], get_open_curiosities=lambda: []))


def test_production_studio_persists_plan_assets_and_reviews(tmp_path):
    studio = ProductionStudio(tmp_path)
    plan = studio.create(
        title="Mary After Midnight",
        objective="A character-consistent short",
        characters=[{"character_id": "mary", "display_name": "Mary", "visual_traits": ["red hair", "blue eyes"]}],
        shots=[{"shot_id": "s1", "duration_s": 4, "framing": "medium", "action": "Mary looks up from her computer", "dialogue": "You're still awake?"}],
    )
    asset = studio.add_asset(plan["production_id"], kind="video_take", uri="project://takes/s1-a", shot_id="s1", provider="example")
    review = studio.review(plan["production_id"], rating="positive", asset_id=asset["id"], note="Keep the expression")

    reloaded = ProductionStudio(tmp_path)
    project = reloaded.get(plan["production_id"])
    assert project["title"] == "Mary After Midnight"
    assert project["assets"][0]["id"] == asset["id"]
    assert project["reviews"][0]["id"] == review["id"]
    assert reloaded.snapshot()["semantics"]["identity_owner"] is False


def test_ecosystem_production_is_canonical_workspace_and_emits_jobs(tmp_path):
    mary = _Mary(tmp_path)
    ecosystem = MaryEcosystem(mary)
    result = ecosystem.apply_workspace_action("production.create", {
        "title": "Fishing Day",
        "objective": "Storyboard a short",
        "shots": [{"shot_id": "s1", "duration_s": 3, "framing": "wide", "action": "Mary casts a fishing line"}],
    })
    production_id = result["production"]["production_id"]
    assert ecosystem.workspace_snapshot()["production"]["projects"] == 1
    jobs = ecosystem.production.jobs(production_id)
    assert jobs["jobs"][0]["kind"] == "video.render"
    assert jobs["jobs"][-1]["kind"] == "edit.assemble"
    assert jobs["ready"] is False


def test_production_and_integration_actions_are_protocol_bounded():
    assert WorkspaceActionRequest.from_dict({"action": "production.create", "args": {"title": "x"}}).action == "production.create"
    assert RuntimeActionRequest.from_dict({"action": "production.jobs.preview", "args": {"production_id": "x"}}).action == "production.jobs.preview"
    assert RuntimeActionRequest.from_dict({"action": "integration.status", "args": {}}).action == "integration.status"
    assert RuntimeActionRequest.from_dict({"action": "training.dataset.preview", "args": {}}).action == "training.dataset.preview"
