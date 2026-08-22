from __future__ import annotations

import json
from pathlib import Path

import pytest

from mary.core.mary import Mary
from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.desktop.integrations import DesktopIntegrationRegistry
from mary.launcher.update import UpdateManifest, UpdateService


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_dashboard_is_a_view_over_canonical_mary_state(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary.user_model.record_profile(
        category="preference",
        key="favorite_color",
        value="blue",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.relationship_history.record_shared_experience(
        "We finished a MaryV2 hardening pass together",
        importance=0.9,
        metadata={"kind": "shared_work"},
    )

    state = build_desktop_dashboard_state(mary, runtime_status="idle")

    assert state["live"]["character"]["name"] == "Mary"
    assert any(item["title"] == "blue" for item in state["memory_highlights"])
    assert state["relationship"]["score"] > 0
    assert state["relationship"]["semantics"].startswith("derived relationship-continuity")
    assert state["paths"]["data_root"] == str(mary.config.paths.data)


def test_dashboard_payload_excludes_test_curiosity_and_secret_names(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary.agency.curiosities.add_curiosity(
        "Learn more about Unbe",
        importance=1.0,
        source="test",
    )

    payload = build_desktop_dashboard_state(mary)
    serialized = json.dumps(payload)

    assert payload["curiosities"] == []
    assert "GROQ_API_KEY" not in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "TAVILY_API_KEY" not in serialized


def test_creative_app_registry_never_accepts_arbitrary_command(monkeypatch, tmp_path) -> None:
    fake = tmp_path / "photoshop.exe"
    fake.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("MARY_PHOTOSHOP_PATH", str(fake))
    registry = DesktopIntegrationRegistry()

    command = registry.build_command("photoshop")
    assert command == [str(fake.resolve())]
    with pytest.raises(ValueError):
        registry.build_command("powershell -enc anything")


def test_update_manifest_requires_verified_http_package() -> None:
    digest = "a" * 64
    manifest = UpdateManifest.from_dict(
        {
            "version": "12.8.0",
            "package_url": "https://example.invalid/MaryV2-12.8.0.zip",
            "sha256": digest,
            "notes": "test",
        }
    )
    assert manifest.version == "12.8.0"
    assert manifest.sha256 == digest

    with pytest.raises(ValueError):
        UpdateManifest.from_dict(
            {
                "version": "12.8.0",
                "package_url": "file:///tmp/update.zip",
                "sha256": digest,
            }
        )


def test_update_service_version_comparison_is_local_and_deterministic() -> None:
    service = UpdateService(manifest_url="", current_version="12.7.0")
    assert service.enabled is False
    assert service.is_newer("12.7.1") is True
    assert service.is_newer("12.7.0") is False
    assert service.is_newer("12.6.9") is False


def test_game_shell_and_launcher_are_local_build_surfaces() -> None:
    root = _root()
    main_html = (root / "desktop" / "index.html").read_text(encoding="utf-8")
    launcher_html = (root / "desktop" / "launcher.html").read_text(encoding="utf-8")
    vite = (root / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    package = json.loads((root / "desktop" / "package.json").read_text(encoding="utf-8"))

    assert "qrc:///qtwebchannel/qwebchannel.js" in main_html
    assert "qrc:///qtwebchannel/qwebchannel.js" in launcher_html
    assert "https://fonts.googleapis.com" not in main_html + launcher_html
    assert "cdn.jsdelivr.net" not in main_html + launcher_html
    assert "launcher: resolve(__dirname, 'launcher.html')" in vite
    assert package["version"] in {"12.7.0", "12.8.0"}
    assert package["dependencies"]["@pixiv/three-vrm"] == "3.5.5"
