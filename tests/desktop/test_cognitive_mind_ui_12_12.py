from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_exposes_local_mind_workspace_and_rebuild_control():
    html = (ROOT / "desktop" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    bridge = (ROOT / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    assert 'data-screen="mind"' in html
    assert "function renderMind()" in js
    assert "Cognitive Reservoir" in js
    assert "rebuildCognitiveReservoir" in bridge
    assert "getMindStatus" in bridge


def test_runtime_surface_shows_local_act_and_delivery_profile():
    js = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    assert "Voice delivery" in js
    assert "Local act" in js
