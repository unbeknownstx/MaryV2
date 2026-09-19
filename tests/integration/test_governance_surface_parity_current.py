from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_governed_world_and_skill_actions_are_available_on_every_creator_surface():
    core = _text("mary/core/service.py")
    desktop_bridge = _text("mary/desktop/bridge.py")
    desktop = _text("desktop/src/main.js")
    mobile_server = _text("mary/mobile/server.py")
    web = _text("mobile_web/app.js")
    native_web = _text("mobile_native/MaryMobile/www/app.js")
    ios_state = _text("ios/MaryV2iOS/Sources/AppState.swift")
    ios = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert web == native_web

    for action in (
        "world.reconcile",
        "continuity.skill.status",
        "continuity.skill.approve",
        "continuity.skill.reject",
        "continuity.skill.revise",
    ):
        assert action in core

    for source in (desktop_bridge, mobile_server, ios_state):
        assert "world.reconcile" in source
        assert "continuity.skill.approve" in source
        assert "continuity.skill.reject" in source
        assert "continuity.skill.revise" in source

    for surface in (desktop, web, ios):
        assert "Keep this as current" in surface
        assert "Approve" in surface
        assert "Reject" in surface
        assert "revision" in surface.lower()

    assert "competing evidence remains historical" in desktop.lower()
    assert "execution permission is unchanged" in web.lower()
    assert "approval and execution permissions remain explicit" in ios.lower()


def test_world_and_skill_review_never_grant_execution_authority():
    core = _text("mary/core/service.py")
    assert '"authority": "explicit creator approval"' in core
    assert '"authority": "explicit creator rejection"' in core
    assert '"promotion_performed": False' in core
    assert '"execution_performed": False' in core
    assert "execution permission remains separate" in core
