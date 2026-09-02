from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_projects_safe_realtime_decision_trace():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    assert "runtime.decision_trace" in source
    assert "Why Mary Did That" in source
    assert "no raw dialogue" in source.casefold()


def test_mobile_projects_same_realtime_decision_trace():
    source = (ROOT / "mobile_web" / "app.js").read_text(encoding="utf-8")
    assert "rt.decision_trace" in source
    assert "WHY MARY DID THAT" in source
    assert "raw dialogue" in source.casefold()
