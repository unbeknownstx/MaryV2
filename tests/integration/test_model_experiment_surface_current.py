from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def _text(path): return (ROOT/path).read_text(encoding="utf-8")
def test_all_frontends_surface_exact_model_trial_readiness():
    desktop=_text("desktop/src/main.js")
    web=_text("mobile_web/app.js")
    native=_text("mobile_native/MaryMobile/www/app.js")
    ios=_text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")
    assert web==native
    assert "Trial-ready experiments" in desktop
    assert "Trial-ready experiments" in web
    assert "Trial-ready experiments" in ios
