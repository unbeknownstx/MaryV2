from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_desktop_can_request_improvement_proposal_without_executing_it():
    bridge = _text("mary/desktop/bridge.py")
    ui = _text("desktop/src/main.js")

    assert "def proposeImprovement(" in bridge
    assert '"continuity.improvement.propose"' in bridge
    assert "data-improvement-kind" in ui
    assert "Propose next step" in ui
    assert "bridge.proposeImprovement" in ui
    assert "Nothing was created or executed" in ui


def test_pwa_and_legacy_mobile_share_proposal_only_improvement_controls():
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")
    server = _text("mary/mobile/server.py")

    assert web == native
    assert "data-improvement-kind" in web
    assert "Propose next step" in web
    assert "bridge('proposeImprovement'" in web
    assert "Nothing was created or executed" in web
    assert 'if name == "proposeImprovement":' in server
    assert '"continuity.improvement.propose"' in server


def test_native_iphone_requests_same_core_proposal_and_keeps_authority_visible():
    state = _text("ios/MaryV2iOS/Sources/AppState.swift")
    view = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert "@Published var improvementProposalData" in state
    assert "func proposeImprovement(kind: String, subject: String)" in state
    assert '"continuity.improvement.propose"' in state
    assert 'Button("Propose next step")' in view
    assert 'Eyebrow(text: "Proposal only")' in view
    assert 'label: "Plan created"' in view
    assert 'label: "Execution performed"' in view
    assert "Nothing is created, permitted, promoted, or executed" in view
