from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_desktop_and_mobile_expose_same_character_runtime_concepts():
    desktop = _text("desktop/src/main.js")
    mobile = _text("mobile_web/app.js")

    # These are product concepts backed by the same Core workspace snapshot.
    concepts = (
        "live scene",
        "adapter lab",
        "world pulse",
    )
    desktop_lower = desktop.lower()
    mobile_lower = mobile.lower()
    for concept in concepts:
        assert concept in desktop_lower, f"desktop missing {concept}"
        assert concept in mobile_lower, f"mobile missing {concept}"

    # Speech arbitration is surfaced on both clients even if wording differs.
    assert "speech" in desktop.lower()
    assert "speech" in mobile.lower()


def test_mobile_bundle_is_not_a_second_character_runtime_owner():
    mobile = _text("mobile_web/app.js")
    # The mobile UI may render Core state, but it must not instantiate the
    # canonical Python runtime/state owners itself.
    forbidden = (
        "MaryApplication(",
        "RelationshipManager(",
        "DevelopedSelfStateStore(",
        "SemanticVectorIndex(",
    )
    for marker in forbidden:
        assert marker not in mobile


def test_remote_safe_workspace_projection_contains_character_runtime_sections():
    source = _text("mary/ecosystem/manager.py")
    required = (
        '"presence"',
        '"world_context"',
        '"world_pulse"',
        '"streaming"',
        '"adapter_lab"',
        '"model_candidates"',
        '"character_runtime"',
    )
    for marker in required:
        assert marker in source, f"workspace projection missing {marker}"
