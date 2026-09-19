from types import SimpleNamespace

import mary.runtime.integration_graph as integration_graph


class _Owner:
    def status(self):
        return {}

    def snapshot(self):
        return {}


def test_integration_graph_does_not_reenter_service_through_system_fabric(monkeypatch):
    mary = SimpleNamespace(
        turn_mind=None,
        realtime=None,
        llm=None,
        system_contract=SimpleNamespace(snapshot=lambda _mary: {"single_llm_router": True}),
        cognition=None,
        reasoning=None,
        reflection=None,
        memory=None,
        growth=None,
        tools=None,
        autonomy=None,
        node_registry=SimpleNamespace(
            update_capability_readiness=lambda *a, **k: True,
            route_preview=lambda *a, **k: {},
        ),
        browser_context_sensor=None,
        game_action_router=None,
        performance_profiles=None,
        capability_invocations=None,
        root_authority=object(),
        character_evaluation=object(),
        training_feedback=object(),
        creative_services=object(),
        performance=None,
        character=None,
        character_sourcebook=None,
        relationship=None,
        agency=None,
        emotion=None,
    )
    application = SimpleNamespace(
        mary=mary,
        ecosystem=SimpleNamespace(
            mary=mary,
            presence=None,
            streaming=None,
            cross_surface=object(),
            action_windows=None,
            adapter_lab=object(),
            production=object(),
        ),
        _ensure_autonomy_started=lambda: None,
        _cycle_autonomy=lambda: None,
        _agency_autonomy_proposal_trigger=lambda: None,
    )
    service = SimpleNamespace(
        application=application,
        mary=mary,
        dashboard_status=lambda: {},
        device_tasks=object(),
        _device_ollama_provider=None,
    )

    calls = []
    def fake_projection(app, *, service=None):
        calls.append(service)
        return {"authority": {"projection": "read_only"}}

    import mary.runtime.system_fabric as system_fabric
    monkeypatch.setattr(system_fabric, "build_system_fabric_projection", fake_projection)

    result = integration_graph.build_integration_graph(application=application, service=service)

    assert calls == [None]
    fabric = next(item for item in result["edges"] if item["name"] == "Core dashboard -> shared read-only system fabric")
    assert fabric["connected"] is True
