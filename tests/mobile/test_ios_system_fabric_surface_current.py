from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_native_iphone_exposes_shared_system_fabric_workspaces():
    models = _text("ios/MaryV2iOS/Sources/Models.swift")
    more = _text("ios/MaryV2iOS/Sources/MoreView.swift")
    app = _text("ios/MaryV2iOS/Sources/AppState.swift")
    detail = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    for name in ("knowledge", "procedures", "modelLab"):
        assert name in models
        assert f"case .{name}:" in app
        assert f"case .{name}:" in detail

    assert ".knowledge, .procedures, .modelLab" in more
    assert 'dashboard["system_fabric"]' in app
    assert "evidence sources" in detail
    assert "approval and execution permissions remain explicit" in detail
    assert "Models and LoRAs are replaceable capabilities" in detail
