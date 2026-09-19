from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_studio_camera_scene_and_capture_controls_are_bound():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert 'id="stage-camera-yaw"' in source
    assert 'id="stage-camera-elevation"' in source
    assert "stageCameraYaw" in source
    assert "stageCameraElevation" in source
    assert "data-stage-scene" in source
    assert "stageRoom = new THREE.Group()" in source
    assert "preserveDrawingBuffer: true" in source

    # Multi-control binding must use querySelectorAll, not one Element.forEach().
    for selector in (
        "data-avatar-frame",
        "data-stage-expression",
        "data-stage-motion",
        "data-stage-lighting",
        "data-stage-scene",
    ):
        assert f"$$('#workspace-body [{selector}]').forEach" in source
        assert f"\n  $('#workspace-body [{selector}]').forEach" not in source


def test_vrm_gaze_uses_real_lookat_target_and_face_expressions_are_model_aware():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "maryPerformanceLookAtTarget" in source
    assert "currentVrm.lookAt.target = lookAtTarget" in source
    assert "currentVrm.lookAt.autoUpdate = true" in source
    assert "updatePerformanceGaze(gazeStyle, delta)" in source

    assert "customExpressionMap" in source
    assert "expressionMap" in source
    assert "resolveFaceExpression" in source
    assert "faceExpressionNames" in source


def test_companion_body_keeps_current_mary_session_and_only_changes_presentation():
    bridge = (ROOT / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    window = (ROOT / "mary" / "desktop" / "window.py").read_text(encoding="utf-8")

    assert "windowPresentationRequested" in bridge
    assert "presentation-only" in bridge.lower()
    assert "WindowStaysOnTopHint" in window
    assert "WA_TranslucentBackground" in window
    assert "self.web.setStyleSheet(\"background: transparent;\")" in window
