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
    monkeypatch.setattr(config_module.sys, "platform", "win32")
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


def test_frozen_macos_default_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "darwin")
    monkeypatch.setattr(config_module.sys, "executable", str(tmp_path / "MaryV2.app" / "Contents" / "MacOS" / "MaryV2"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARY_DATA_DIR", raising=False)
    monkeypatch.delenv("MARY_PORTABLE", raising=False)

    paths = config_module.PathConfig(root=tmp_path / "bundle")

    assert paths.data == tmp_path / "home" / "Library" / "Application Support" / "MaryV2" / "data"
    assert paths.data != paths.root / "data"


def test_frozen_linux_default_respects_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "linux")
    monkeypatch.setattr(config_module.sys, "executable", str(tmp_path / "MaryV2"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("MARY_DATA_DIR", raising=False)
    monkeypatch.delenv("MARY_PORTABLE", raising=False)

    paths = config_module.PathConfig(root=tmp_path / "bundle")

    assert paths.data == tmp_path / "xdg" / "MaryV2" / "data"


def test_frozen_macos_env_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "darwin")
    monkeypatch.setattr(config_module.sys, "executable", str(tmp_path / "MaryV2.app" / "Contents" / "MacOS" / "MaryV2"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARY_ENV_FILE", raising=False)
    monkeypatch.delenv("MARY_PORTABLE", raising=False)

    assert config_module._dotenv_path() == (
        tmp_path / "home" / "Library" / "Application Support" / "MaryV2" / ".env"
    )


def test_frozen_windows_keeps_existing_side_by_side_env(monkeypatch, tmp_path):
    executable = tmp_path / "MaryV2.exe"
    executable.write_text("", encoding="utf-8")
    side_by_side = tmp_path / ".env"
    side_by_side.write_text("MARY_DEBUG=false\n", encoding="utf-8")

    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "win32")
    monkeypatch.setattr(config_module.sys, "executable", str(executable))
    monkeypatch.delenv("MARY_ENV_FILE", raising=False)
    monkeypatch.delenv("MARY_PORTABLE", raising=False)

    assert config_module._dotenv_path() == side_by_side


def test_source_checkout_default_state_is_outside_repository(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "frozen", False, raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delenv("MARY_DATA_DIR", raising=False)
    monkeypatch.delenv("MARY_PORTABLE", raising=False)
    monkeypatch.delenv("MARY_WORKSPACE_ROOT", raising=False)

    paths = config_module.PathConfig(root=tmp_path / "repo")

    assert paths.data == tmp_path / "LocalAppData" / "MaryV2" / "data"
    assert paths.data != paths.root / "data"
    assert paths.workspace == paths.data / "workspace"
