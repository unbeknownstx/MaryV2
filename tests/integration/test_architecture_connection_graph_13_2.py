from mary.core.service import MaryCoreService
from mary.core.mary import Mary
from mary.runtime.application import create_application
from mary.runtime.integration_graph import build_integration_graph


def test_full_runtime_connection_graph_has_no_required_disconnects(tmp_path):
    mary = Mary()
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed_self.json",
        preference_promotion_path=tmp_path / "personality" / "preference_promotion.json",
        knowledge_path=tmp_path / "knowledge" / "knowledge.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
        name="connection_graph_test",
    )
    service = MaryCoreService(app, instance_id="connection-test")
    graph = build_integration_graph(application=app, service=service)
    try:
        assert graph["healthy"] is True, graph["required_failures"]
        assert graph["required_failures"] == []
        names = {item["name"] for item in graph["edges"] if item["connected"]}
        assert "TurnMind -> character" in names
        assert "TurnMind -> relationship" in names
        assert "TurnMind -> agency" in names
        assert "TurnMind -> autonomy" in names
        assert "Presence -> realtime attention bus" in names
        assert "production workspace -> canonical ecosystem" in names
        assert "device task broker -> Core service" in names
    finally:
        service.close()
