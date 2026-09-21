from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_13_75_system_fabric_combines_evidence_gaps_without_new_authority():
    fabric = _text("mary/runtime/system_fabric.py")
    assert "def _improvement_agenda(" in fabric
    assert "def _live_scene_summary(" in fabric
    assert '"improvement_agenda": improvement_agenda' in fabric
    assert '"live_scene": dict(live_scene or {})' in fabric
    assert '"automatic_execution": False' in fabric
    assert '"automatic_permission": False' in fabric
    assert '"automatic_model_promotion": False' in fabric
    assert '"authority": "read_only_evidence_agenda"' in fabric
    assert '"authority": "ephemeral_context_only"' in fabric


def test_13_75_desktop_pwa_and_legacy_shell_expose_same_convergence_language():
    desktop = _text("desktop/src/main.js")
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")

    assert web == native
    assert "const nodeIntelligence = compute.node_intelligence || {};" in desktop
    assert "const authorizedCaps =" in desktop
    assert "const demonstratedCaps =" in desktop
    assert "Evidence Improvement Agenda" in desktop
    assert "Embodiment + Live Presence" in desktop
    assert "capability_contract" in desktop
    assert "improvement_agenda" in desktop

    assert "IMPROVEMENT AGENDA" in web
    assert "EMBODIMENT + PRESENCE" in web
    assert "capability_contract" in web
    assert "improvement_agenda" in web
    assert "automatic permission" not in web.lower()


def test_13_75_native_iphone_reads_shared_fabric_not_a_second_state_owner():
    app_state = _text("ios/MaryV2iOS/Sources/AppState.swift")
    workspace = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert 'liveData = CoreProjection.dict(dashboard["system_fabric"])' in app_state
    assert 'compute["capability_contract"]' in app_state
    assert "Intelligence convergence" in workspace
    assert "What Mary can prove next" in workspace
    assert "Embodiment + live presence" in workspace
    assert "Regression readiness" in workspace
    assert "Scene persistence" in workspace
    assert "read-only evidence agenda" in workspace
    assert "cannot grant permission or execute the work" in workspace
