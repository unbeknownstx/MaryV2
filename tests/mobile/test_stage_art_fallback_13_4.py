from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generated_mary_art_is_available_to_native_ios_stage():
    resources = ROOT / "ios" / "MaryV2iOS" / "Resources"
    for name in (
        "mary-reference.jpeg",
        "mary-stream-room-reference.png",
        "mary-neon-night-manga.png",
        "mary-neon-reference-sheet.png",
    ):
        assert (resources / name).is_file(), name

    swift = (ROOT / "ios" / "MaryV2iOS" / "Sources" / "MaryStageArtwork.swift").read_text(encoding="utf-8")
    assert "mary-stream-room-reference" in swift
    assert "mary-neon-night-manga" in swift
    assert "mary-neon-reference-sheet" in swift
    assert "presentation-only" in swift


def test_mobile_web_and_legacy_wrapper_share_generated_stage_fallbacks():
    web = ROOT / "mobile_web"
    native = ROOT / "mobile_native" / "MaryMobile" / "www"

    for name in ("index.html", "style.css", "app.js", "sw.js"):
        assert (web / name).read_bytes() == (native / name).read_bytes()

    html = (web / "index.html").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    assert "mary-stream-room-reference.png" in html
    assert "mary-neon-night-manga.png" in html
    assert "mary-stage-art-cycle" in css
    assert "/v1/voice/synthesize" in js
    assert "CURRENT WORK" in js


def test_desktop_vrm_keeps_generated_art_fallback():
    html = (ROOT / "desktop" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "desktop" / "src" / "style.css").read_text(encoding="utf-8")
    main = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "MaryCosma.vrm" in main
    assert "loadMaryVrm" in main
    assert "avatar-fallback" in html
    assert "mary-stream-room-reference.png" in html
    assert "mary-neon-night-manga.png" in html
    assert "mary-fallback-art-cycle" in css
