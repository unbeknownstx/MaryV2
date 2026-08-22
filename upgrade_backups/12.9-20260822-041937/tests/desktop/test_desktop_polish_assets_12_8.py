from pathlib import Path


def test_first_program_polish_assets_are_packaged():
    root = Path(__file__).resolve().parents[2]
    expected = [
        "desktop/public/assets/ui/presence-orb.svg",
        "desktop/public/assets/ui/hud-corners.svg",
        "desktop/public/assets/ui/holo-scan.svg",
        "desktop/public/assets/ui/cursor.svg",
        "desktop/public/assets/ui/cursor-active.svg",
        "desktop/public/assets/backgrounds/cyber-grid.svg",
        "desktop/public/assets/backgrounds/focus-rain.svg",
        "desktop/public/assets/backgrounds/study-grid.svg",
        "desktop/public/assets/backgrounds/stream-mesh.svg",
        "desktop/design/MARY_12_8_LIVE_GUI_TARGET.png",
        "desktop/ASSET_LICENSES.md",
    ]
    for relative in expected:
        assert (root / relative).is_file(), relative


def test_launcher_static_fallback_tracks_current_release():
    root = Path(__file__).resolve().parents[2]
    html = (root / "desktop" / "launcher.html").read_text(encoding="utf-8")
    assert 'id="installed-version">12.9.0<' in html
    assert 'id="desktop-phase">desktop-uplift-runtime<' in html
