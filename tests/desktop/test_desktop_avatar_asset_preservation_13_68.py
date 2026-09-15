from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


from mary.desktop.frontend_build import (
    _configured_vrm_path,
    _preserve_local_avatar_assets,
    _restore_local_avatar_assets,
    avatar_asset_status,
    ensure_desktop_frontend,
)


def test_frontend_build_preserves_gitignored_vrm_from_old_dist(tmp_path):
    root = tmp_path
    old = root / "desktop" / "dist" / "models" / "MaryCosma.vrm"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"VRM" + b"x" * 4096)

    staging = root / "stage"
    preserved = _preserve_local_avatar_assets(root, staging)
    assert [path.name for path in preserved] == ["MaryCosma.vrm"]

    old.unlink()
    _restore_local_avatar_assets(root, preserved)

    assert (root / "desktop" / "dist" / "models" / "MaryCosma.vrm").is_file()
    assert (root / "desktop" / "public" / "models" / "MaryCosma.vrm").is_file()


def test_explicit_vrm_path_can_reseed_missing_public_asset(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    external = tmp_path / "MaryCosma.vrm"
    external.write_bytes(b"VRM" + b"y" * 4096)
    monkeypatch.setenv("MARY_DESKTOP_VRM_PATH", str(external))

    assert _configured_vrm_path(root) == external.resolve()
    preserved = _preserve_local_avatar_assets(root, tmp_path / "stage")
    _restore_local_avatar_assets(root, preserved)

    status = avatar_asset_status(root)
    assert status["configured"] is True
    assert status["public_ready"] is True
    assert status["built_ready"] is True


def test_missing_personal_vrm_is_reported_without_fabricating_one(tmp_path, monkeypatch):
    monkeypatch.delenv("MARY_DESKTOP_VRM_PATH", raising=False)
    monkeypatch.delenv("MARY_MODEL_DIR", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    status = avatar_asset_status(tmp_path)
    assert status == {
        "configured": False,
        "public_ready": False,
        "built_ready": False,
        "filename": "MaryCosma.vrm",
        "source": "missing",
    }




def test_downloaded_vrm_is_seeded_even_when_frontend_is_current(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    desktop = root / "desktop"
    dist = desktop / "dist"
    dist.mkdir(parents=True)
    built_page = dist / "index.html"
    built_page.write_text("<html></html>", encoding="utf-8")

    fake_home = tmp_path / "home"
    downloads = fake_home / "Downloads"
    downloads.mkdir(parents=True)
    downloaded = downloads / "MaryCosma.vrm"
    downloaded.write_bytes(b"VRM" + b"z" * 4096)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.delenv("MARY_DESKTOP_VRM_PATH", raising=False)
    monkeypatch.delenv("MARY_MODEL_DIR", raising=False)

    page = ensure_desktop_frontend(root)

    assert page == built_page
    assert (desktop / "public" / "models" / "MaryCosma.vrm").read_bytes() == downloaded.read_bytes()
    assert (desktop / "dist" / "models" / "MaryCosma.vrm").read_bytes() == downloaded.read_bytes()


def test_companion_stage_hides_raw_avatar_fetch_errors():
    main = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    assert "Portrait mode · 3D avatar unavailable" in main
    assert "`VRM fallback · ${avatarLoadError.slice" not in main
    assert "console.warn('MaryCosma.vrm was not loaded:', error)" in main
