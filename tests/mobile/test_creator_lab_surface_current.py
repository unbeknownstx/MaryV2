from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def _text(path): return (ROOT/path).read_text(encoding="utf-8")
def test_pwa_creator_lab_uses_bounded_core_vision_and_canonical_social_authoring():
    web=_text("mobile_web/app.js")
    native=_text("mobile_native/MaryMobile/www/app.js")
    assert web==native
    assert "prepareCreatorImage" in web
    assert "/api/creator-image/describe" in web
    assert "bridge('proposeSocial'" in web
    assert "playMarySpeech" in web
    assert "1350000" in web
    assert "Nothing is published automatically" in web
    assert "Raw pixels stay ephemeral task input" in web
def test_pwa_creator_lab_does_not_persist_image_bytes_to_local_storage():
    web=_text("mobile_web/app.js")
    assert "localStorage.setItem('mary.creatorLab" not in web
    assert 'localStorage.setItem("mary.creatorLab' not in web
