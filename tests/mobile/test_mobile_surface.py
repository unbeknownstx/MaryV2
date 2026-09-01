from pathlib import Path
from types import SimpleNamespace

from mary.mobile.server import _is_loopback, _missing_static_assets, _resolve_auth


def test_loopback_does_not_require_generated_token(tmp_path, monkeypatch):
    monkeypatch.delenv("MARY_MOBILE_TOKEN", raising=False)
    auth = _resolve_auth(host="127.0.0.1", data_root=tmp_path)
    assert auth.enabled is False
    assert auth.source == "loopback"


def test_non_loopback_generates_and_reuses_token(tmp_path, monkeypatch):
    monkeypatch.delenv("MARY_MOBILE_TOKEN", raising=False)
    first = _resolve_auth(host="0.0.0.0", data_root=tmp_path)
    second = _resolve_auth(host="0.0.0.0", data_root=tmp_path)
    assert first.enabled is True
    assert len(first.token) >= 24
    assert second.token == first.token
    assert first.token_path == Path(tmp_path) / "mobile" / "access_token.txt"


def test_environment_token_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_MOBILE_TOKEN", "configured-secret")
    auth = _resolve_auth(host="0.0.0.0", data_root=tmp_path)
    assert auth.token == "configured-secret"
    assert auth.source == "environment"
    assert auth.token_path is None


def test_mobile_static_root_prefers_phone_ui_even_if_desktop_is_built(tmp_path):
    from mary.mobile.server import _static_root

    (tmp_path / "mobile_web").mkdir()
    (tmp_path / "mobile_web" / "index.html").write_text("mobile", encoding="utf-8")
    (tmp_path / "desktop" / "dist").mkdir(parents=True)
    (tmp_path / "desktop" / "dist" / "index.html").write_text("desktop", encoding="utf-8")

    assert _static_root(tmp_path) == (tmp_path / "mobile_web")


def test_complete_mobile_shell_has_no_missing_linked_assets():
    root = Path(__file__).resolve().parents[2]
    index = (root / "mobile_web" / "index.html").read_text(encoding="utf-8")

    assert _missing_static_assets(root / "mobile_web") == []
    assert 'rel="icon" href="./assets/mary-icon.png"' in index
