from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pwa_and_native_web_shell_share_system_fabric_surface():
    web_app = _text("mobile_web/app.js")
    native_app = _text("mobile_native/MaryMobile/www/app.js")
    web_html = _text("mobile_web/index.html")
    native_html = _text("mobile_native/MaryMobile/www/index.html")

    assert web_app == native_app
    assert web_html == native_html
    assert "function renderFabric()" in web_app
    assert "system_fabric" in web_app
    assert 'data-open="fabric"' in web_html
    assert "System Fabric" in web_html
