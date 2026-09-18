from pathlib import Path

from mary.mobile.server import MOBILE_PROTOCOL_VERSION


ROOT = Path(__file__).resolve().parents[2]


def test_pwa_tracks_current_core_contract_without_pinning_legacy_architecture():
    app = (ROOT / "mobile_web" / "app.js").read_text(encoding="utf-8")
    worker = (ROOT / "mobile_web" / "sw.js").read_text(encoding="utf-8")

    assert MOBILE_PROTOCOL_VERSION == "4"
    assert "remote_mary_core" in app
    assert "registerSurface" in app
    assert "setPerformanceContext" in app
    assert "13.3 Unified Core Client" not in app
    assert "13.3 Mary Core" not in app
    assert "Mary 13.3 performs" not in app
    assert "core.architecture||'current'" in app
    assert "v13-68-core-sync-20260917" in worker


def test_pwa_and_compatibility_web_bundle_keep_current_surface_files_aligned():
    web = ROOT / "mobile_web"
    compat = ROOT / "mobile_native" / "MaryMobile" / "www"

    for name in ("app.js", "sw.js", "polish-13-7.css"):
        assert (web / name).read_bytes() == (compat / name).read_bytes()


def test_pwa_stage_art_is_full_bleed_and_chat_rail_is_bounded():
    css = (ROOT / "mobile_web" / "polish-13-7.css").read_text(encoding="utf-8")

    assert "object-fit: cover !important;" in css
    assert "max-width: none !important;" in css
    assert "height: 32% !important;" in css
    assert "max-height: 330px;" in css
