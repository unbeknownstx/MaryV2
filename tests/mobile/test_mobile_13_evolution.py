from pathlib import Path


def test_mobile_13_surface_has_growth_conversation_modes_and_voice_lab():
    root = Path(__file__).resolve().parents[2]
    html = (root / "mobile_web" / "index.html").read_text(encoding="utf-8")
    js = (root / "mobile_web" / "app.js").read_text(encoding="utf-8")
    assert 'data-open="growth"' in html
    assert 'data-conversation-mode="engaged"' in html
    assert 'data-conversation-mode="deep"' in html
    assert "renderGrowth" in js
    assert "saveVoiceProfile" in js
    assert "resetVoiceBaseline" in js
    assert "DISLIKES / AVERSIONS" in js


def test_mobile_protocol_is_13_generation():
    from mary.mobile.server import MOBILE_PROTOCOL_VERSION
    assert MOBILE_PROTOCOL_VERSION in {"3", "4"}
