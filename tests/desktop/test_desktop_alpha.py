from __future__ import annotations

import json
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_desktop_frontend_manifest_is_pinned_and_local() -> None:
    package = json.loads((_root() / "desktop" / "package.json").read_text(encoding="utf-8"))

    assert package["dependencies"]["three"] == "0.185.1"
    assert package["dependencies"]["@pixiv/three-vrm"] == "3.5.5"
    assert package["devDependencies"]["vite"] == "8.2.1"
    assert package["scripts"]["build"] == "vite build"


def test_desktop_build_uses_relative_asset_base_for_qt_file_url() -> None:
    source = (_root() / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    assert "base: './'" in source


def test_desktop_bridge_uses_canonical_application_not_second_mary() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    assert "MaryApplication" in source
    assert "Mary(" not in source
    assert "self.application.run" in source


def test_vrm_orientation_and_relaxed_pose_are_version_safe() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "VRMUtils.rotateVRM0(currentVrm)" in source
    assert "currentVrm.scene.rotation.y = Math.PI" not in source
    assert "setNormalizedPose" in source
    assert "RELAXED_STANDING_POSE" in source
    assert "new THREE.Clock" not in source


def test_desktop_bridge_does_not_pass_avatar_state_as_expression() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")

    assert "mary.avatar.sync_emotion()" in source
    assert "expression = mary.avatar.sync_emotion()" not in source
    assert "expression=expression" not in source


def test_relaxed_pose_lowers_arms_from_t_pose() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "leftUpperArm: { rotation: quaternionArrayFromEuler(0, 0, -1.28) }" in source
    assert "rightUpperArm: { rotation: quaternionArrayFromEuler(0, 0, 1.28) }" in source
