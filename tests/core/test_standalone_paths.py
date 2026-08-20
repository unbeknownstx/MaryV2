from __future__ import annotations

from pathlib import Path

from mary.core import config as config_module


def test_explicit_data_and_workspace_paths_override_defaults(monkeypatch, tmp_path):
    data = tmp_path / "state"
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MARY_DATA_DIR", str(data))
    monkeypatch.setenv("MARY_WORKSPACE_ROOT", str(workspace))

    paths = config_module.PathConfig(root=tmp_path / "resources")

    assert paths.data == data.resolve()
    assert paths.workspace == workspace.resolve()


def test_frozen_default_uses_localappdata_not_bundled_resource_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "executable", str(tmp_path / "MaryV2.exe"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delenv("MARY_DATA_DIR", raising=False)
    monkeypatch.delenv("MARY_PORTABLE", raising=False)

    paths = config_module.PathConfig(root=tmp_path / "bundle")

    assert paths.data == tmp_path / "LocalAppData" / "MaryV2" / "data"
    assert paths.data != paths.root / "data"


def test_portable_frozen_mode_keeps_state_beside_executable(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "executable", str(tmp_path / "MaryV2.exe"))
    monkeypatch.setenv("MARY_PORTABLE", "1")
    monkeypatch.delenv("MARY_DATA_DIR", raising=False)

    paths = config_module.PathConfig(root=tmp_path / "bundle")

    assert paths.data == tmp_path / "data"
