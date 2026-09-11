from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_static_server_requests_portrait_mode_on_macos_contract():
    text = (ROOT / "mary" / "desktop" / "static_server.py").read_text(encoding="utf-8")
    assert 'MARY_DESKTOP_MAC_RENDERER' in text
    assert 'sys.platform == "darwin"' in text
    assert 'mary_renderer' in text
    assert '"portrait"' in text
    assert '"webgl"' in text


def test_vite_build_injects_optional_renderer_and_boot_watchdog():
    text = (ROOT / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    assert "mary-safe-renderer" in text
    assert "rendererMode === 'portrait'" in text
    assert "WebGL avatar renderer unavailable; using portrait fallback" in text
    assert "if (!renderer || !canvas) return;" in text
    assert "if (renderer) renderer.render(scene, camera);" in text
    assert "Desktop frontend did not start" in text
    assert "unhandledrejection" in text
    assert "marker missing" in text


def test_macos_launcher_rebuilds_stale_desktop_bundle():
    text = (ROOT / "scripts" / "launch_macos.sh").read_text(encoding="utf-8")
    assert "desktop/dist/index.html" in text
    assert "npm run build" in text
    assert '-newer "$DIST_INDEX"' in text
