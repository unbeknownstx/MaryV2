from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_frontends_surface_exact_model_trial_readiness_and_explicit_execution():
    desktop = _text("desktop/src/main.js")
    desktop_bridge = _text("mary/desktop/bridge.py")
    mobile_server = _text("mary/mobile/server.py")
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")
    ios = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")
    ios_state = _text("ios/MaryV2iOS/Sources/AppState.swift")

    assert web == native

    for surface in (desktop, web, ios):
        assert "Trial-ready experiments" in surface
        assert "Run bounded trial" in surface
        assert "experimental output" in surface.lower()

    assert "model.experiment.dispatch" in desktop_bridge
    assert "getCapabilityTaskStatus" in desktop_bridge
    assert "model.experiment.dispatch" in mobile_server
    assert "getCapabilityTaskStatus" in mobile_server
    assert "model.experiment.dispatch" in ios_state
    assert "capabilityTaskStatus(taskID)" in ios_state

    for source in (desktop_bridge, mobile_server, ios_state):
        assert "max_tokens" in source
        assert "temperature" in source

    assert "production response" in desktop
    assert "production response" in web
    assert "production response" in ios
