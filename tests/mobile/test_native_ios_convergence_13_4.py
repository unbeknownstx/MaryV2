from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IOS = ROOT / "ios" / "MaryV2iOS"
SOURCES = IOS / "Sources"


def read(name: str) -> str:
    return (SOURCES / name).read_text(encoding="utf-8")


def test_native_app_is_direct_core_not_replit_or_webview():
    client = read("MaryCoreClient.swift")
    root = read("RootView.swift")
    all_swift = "\n".join(p.read_text(encoding="utf-8") for p in SOURCES.glob("*.swift"))
    assert "/v1/turn" in client
    assert "WKWebView" not in all_swift
    assert "replit" not in all_swift.lower()
    assert "BottomBar" in root


def test_credentials_are_keychain_backed():
    config = read("AppConfiguration.swift")
    assert "KeychainStore" in config
    assert "mary.core.token" in config


def test_navigation_has_one_modal_authority():
    state = read("AppState.swift")
    root = read("RootView.swift")
    assert "presentedSheet" in state
    assert root.count(".sheet(") == 1
    assert "navigationDestination(for: WorkspaceKind.self)" in root


def test_pwa_primary_interaction_model_is_native():
    chat = read("ChatView.swift")
    models = read("Models.swift")
    for label in ("AUTO", "TALK", "DEEP"):
        assert label in models
    for symbol in ("home", "chat", "command", "focus", "more"):
        assert symbol in models.lower()
    assert "MaryStageView" in chat
    assert "Message Mary" in chat


def test_stage_has_asset_catalog_and_raw_fallbacks():
    stage = read("MaryStageArtwork.swift")
    project = (IOS / "project.yml").read_text(encoding="utf-8")
    assert 'assetName: "MaryPortrait"' in stage
    assert 'rawName: "mary-reference"' in stage
    assert "FileManager.default.enumerator" in stage
    assert "Resources/Assets.xcassets" in project
    assert "Resources/mary-reference.jpeg" in project
    assert (IOS / "Resources" / "Assets.xcassets" / "MaryPortrait.imageset").is_dir()


def test_voice_and_realtime_are_core_backed():
    client = read("MaryCoreClient.swift")
    for route in ("/v1/voice/status", "/v1/voice/synthesize", "/v1/runtime/action"):
        assert route in client


def test_workspace_and_node_capability_routes_exist():
    client = read("MaryCoreClient.swift")
    for route in (
        "/v1/workspace",
        "/v1/workspace/action",
        "/v1/nodes",
        "/v1/nodes/route",
        "/v1/nodes/task/preview",
        "/v1/nodes/task/dispatch",
    ):
        assert route in client


def test_no_obsolete_mobile_token_contract():
    all_swift = "\n".join(p.read_text(encoding="utf-8") for p in SOURCES.glob("*.swift"))
    assert "MARY_MOBILE_TOKEN" not in all_swift
    assert "/api/chat" not in all_swift
    assert "/api/health" not in all_swift
