from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_system_fabric_surfaces_knowledge_substrate_health_without_auto_rebuild():
    fabric = _text("mary/runtime/system_fabric.py")
    desktop = _text("desktop/src/main.js")
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")
    ios = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert web == native
    assert '"substrate": knowledge_intelligence' in fabric
    assert '"substrate_profile"' in fabric

    for surface in (desktop, web, ios):
        assert "Knowledge tiers" in surface
        assert "Knowledge attention" in surface
        assert "Stale local indexes" in surface
        assert "Stale semantic derivatives" in surface

    assert "automatic_rebuild_performed" in _text("mary/knowledge/fabric.py")
    assert "automatic_scan_performed" in _text("mary/knowledge/fabric.py")
