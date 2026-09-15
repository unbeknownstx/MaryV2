from __future__ import annotations

from pathlib import Path

from mary.desktop.frontend_build import (
    _configured_vrm_path,
    _preserve_local_avatar_assets,
    _restore_local_avatar_assets,
    avatar_asset_status,
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
    status = avatar_asset_status(tmp_path)
    assert status == {
        "configured": False,
        "public_ready": False,
        "built_ready": False,
        "filename": "MaryCosma.vrm",
        "source": "missing",
    }
