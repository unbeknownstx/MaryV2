from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_desktop_uses_official_three_vrm_animation_runtime():
    package = json.loads((ROOT / "desktop" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "desktop" / "package-lock.json").read_text(encoding="utf-8"))
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert package["dependencies"]["@pixiv/three-vrm-animation"] == "3.5.5"
    assert lock["packages"][""]["dependencies"]["@pixiv/three-vrm-animation"] == "3.5.5"
    animation = lock["packages"]["node_modules/@pixiv/three-vrm-animation"]
    assert animation["version"] == "3.5.5"
    assert animation["license"] == "MIT"
    assert "VRMAnimationLoaderPlugin" in source
    assert "createVRMAnimationClip" in source
    assert "VRMLookAtQuaternionProxy" in source


def test_vrma_manifest_is_local_allowlisted_and_has_procedural_fallback():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    manifest = json.loads(
        (ROOT / "desktop" / "public" / "motions" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["authority"] == "presentation_assets_only"
    assert "loadMotionManifest" in source
    assert "parsed.origin !== window.location.origin" in source
    assert "!parsed.pathname.includes('/motions/')" in source
    assert "vrmaFailedMotions" in source
    assert "procedural fallback remains active" in source
    assert "syncVrmaMotion" in source
    assert "applySemanticMotionLayer" in source


def test_semantic_motion_transitions_are_layered_not_hard_snaps():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "semanticMotionBlend" in source
    assert "blendPoseRotation" in source
    assert ".slerp(" in source
    assert "transition instead of a skeleton snap" in source
