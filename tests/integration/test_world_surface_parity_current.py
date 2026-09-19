from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_world_evidence_loop_remains_core_owned_and_explicit():
    core = _text("mary/core/service.py")
    protocol = _text("mary/protocol/models.py")

    for action in (
        "world.status",
        "world.refresh_plan",
        "world.ingest",
        "world.accept_evidence",
        "world.reconcile",
    ):
        assert action in protocol
        assert f'action.action == "{action}"' in core

    assert "explicit evidence acceptance only" in core
    assert "explicit reconciliation only" in core
    assert "external context never promotes itself automatically" in core


def test_desktop_and_mobile_surface_world_pulse_freshness_without_truth_authority():
    desktop = _text("desktop/src/main.js")
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")

    assert web == native

    for surface in (desktop, web):
        assert "world_context" in surface
        assert "world_pulse" in surface
        assert "Refresh lanes due" in surface
        assert "External context" in surface
        assert "Current beliefs" in surface
        assert "Temporal relations" in surface

    assert "World Pulse plans refreshes only" in desktop
    assert "World Pulse plans refreshes only" in web
    assert "accepted evidence and reconciliation remain explicit Core actions" in web


def test_native_iphone_world_surface_projects_context_pulse_beliefs_and_history():
    state = _text("ios/MaryV2iOS/Sources/AppState.swift")
    detail = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert 'runtimeAction("world.status")' in state
    assert "case .world: worldCard" in detail
    assert 'app.liveData["context"]' in detail
    assert 'app.liveData["pulse"]' in detail
    assert 'app.liveData["beliefs"]' in detail
    assert 'app.liveData["temporal"]' in detail
    assert 'app.liveData["contradictions"]' in detail
    assert 'Eyebrow(text: "World pulse")' in detail
    assert 'DataRow(label: "Refresh lanes due"' in detail
    assert 'DataRow(label: "Current beliefs"' in detail
    assert 'DataRow(label: "Contradictions"' in detail
    assert "cannot promote itself into Mary truth" in detail
    assert "acceptance and reconciliation remain explicit Core actions" in detail
