from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_world_and_skill_governance_remain_core_owned_and_explicit():
    core = _text("mary/core/service.py")
    protocol = _text("mary/protocol/models.py")

    for action in (
        "world.reconcile",
        "continuity.skill.status",
        "continuity.skill.revise",
        "continuity.skill.approve",
        "continuity.skill.reject",
    ):
        assert action in protocol
        assert f'action.action == "{action}"' in core

    assert "competing beliefs are retired as history rather than deleted" in core
    assert "review candidate only" in core
    assert "explicit creator approval" in core
    assert "explicit creator rejection" in core


def test_desktop_pwa_and_native_iphone_expose_governed_review_without_execution_grants():
    desktop = _text("desktop/src/main.js")
    desktop_bridge = _text("mary/desktop/bridge.py")
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")
    mobile_bridge = _text("mary/mobile/server.py")
    ios = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")
    ios_state = _text("ios/MaryV2iOS/Sources/AppState.swift")

    assert web == native

    assert "World Reconciliation" in desktop
    assert "Procedure Review" in desktop
    assert "WORLD RECONCILIATION" in web
    assert "PROCEDURE REVIEW" in web
    assert "World reconciliation" in ios
    assert "Procedure review" in ios

    for source in (desktop_bridge, mobile_bridge, ios_state):
        assert "world.reconcile" in source
        assert "continuity.skill.approve" in source
        assert "continuity.skill.reject" in source
        assert "continuity.skill.revise" in source

    for surface in (desktop, web, ios):
        assert "permission" in surface.lower()
        assert "history" in surface.lower()


def test_revision_ui_preserves_review_before_replacement():
    desktop = _text("desktop/src/main.js")
    web = _text("mobile_web/app.js")
    ios = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert "Propose revision" in desktop
    assert "Revision candidate created" in desktop
    assert "data-skill-revise" in web
    assert "Revision candidate created" in web
    assert "Create revision candidate" in ios
