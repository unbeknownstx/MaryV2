from mary.core.service import MaryCoreService
from mary.runtime.application import create_application
from mary.runtime.integration_graph import build_integration_graph


def test_full_runtime_connection_graph_has_no_required_disconnects(tmp_path):
    app = create_application(
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
        edges = {item["name"]: item for item in graph["edges"]}
        names = {name for name, item in edges.items() if item["connected"]}
        assert "TurnMind -> character" in names
        assert "TurnMind -> relationship" in names
        assert "TurnMind -> agency" in names
        assert "TurnMind -> autonomy" in names
        assert "cognition/reasoning/reflection -> shared LLM router" in names
        assert "MemoryManager retrieval -> canonical memory stores" in names
        assert "MemoryManager consolidation -> canonical memory and retrieval" in names
        assert "GrowthEngine -> canonical Mary" in names
        assert "GrowthEngine -> canonical memory" in names
        assert "GrowthEngine -> canonical preference promotion" in names
        assert "ToolManager -> canonical tool registry" in names
        assert "MaryApplication -> canonical autonomy" in names
        assert "MaryApplication -> proposal-only autonomy policy" in names
        assert "Presence -> realtime attention bus" in names
        assert "attention -> shared realtime decision trace" in names
        assert "streaming -> canonical presence" in names
        assert "streaming -> shared speaker scheduler" in names
        assert "realtime -> confirmed VAD barge-in gate" in names
        assert "ecosystem -> bounded cross-surface awareness" in names
        assert "ecosystem -> bounded dynamic action windows" in names
        assert "ecosystem -> model adapter lab" in names
        assert "node routing -> capability readiness" in names
        assert "production workspace -> canonical ecosystem" in names
        assert "device task broker -> Core service" in names
        assert edges["device broker/provider -> canonical node registry"]["connected"] is True
        assert edges["device broker/provider -> canonical node registry"]["required"] is False

        original_router = app.mary.reasoning.llm
        app.mary.reasoning.llm = object()
        try:
            disconnected = build_integration_graph(application=app, service=service)
            broken_edge = next(
                item
                for item in disconnected["edges"]
                if item["name"] == "cognition/reasoning/reflection -> shared LLM router"
            )
            assert broken_edge["connected"] is False
            assert broken_edge["name"] in disconnected["required_failures"]
        finally:
            app.mary.reasoning.llm = original_router
    finally:
        service.close()
        app.close()
