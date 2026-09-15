from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IOS = ROOT / "ios" / "MaryV2iOS"
SOURCES = IOS / "Sources"


def _text(name: str) -> str:
    return (SOURCES / name).read_text(encoding="utf-8")


def test_native_iphone_has_five_primary_product_destinations_and_preserves_focus():
    models = _text("Models.swift")
    root = _text("RootView.swift")
    assert "case home, chat, together, work, focus, more" in models
    assert "primaryTabs: [MainTab] = [.home, .chat, .together, .work, .more]" in models
    assert "case .together: TogetherView()" in root
    assert "case .focus: FocusView()" in root
    assert "ForEach(MainTab.primaryTabs)" in root


def test_together_surface_projects_core_relationship_without_owning_it():
    together = _text("TogetherView.swift")
    projection = _text("CoreProjection.swift")
    assert "CoreProjection.relationalSnapshot(app.dashboardData)" in together
    assert 'hardening["relational_presence"]' in projection
    assert 'presence["relationship_mode"]' in projection
    assert "relationship.set_mode" not in together
    assert "relationship.json" not in together
    assert "not another persona" in together


def test_shared_life_actions_are_conversation_first_until_core_write_action_exists():
    state = _text("AppState.swift")
    models = _text("Models.swift")
    assert "func prepareSharedActivity" in state
    assert "draft = activity.prompt" in state
    assert "selectedTab = .chat" in state
    for activity in ("watch", "game", "create", "study", "work", "music", "date", "unwind"):
        assert activity in models


def test_native_chat_is_conversation_first_and_voice_remains_reachable():
    chat = _text("ChatView.swift")
    assert 'Text("Talk with Mary")' in chat
    assert 'app.modalRoute = .voiceCall' in chat
    assert 'TextField("Message Mary…"' in chat
    assert "MaryTypingBubble" in chat
    assert "starterChips" in chat


def test_native_voice_call_exposes_relationship_and_private_public_projection():
    voice = _text("VoiceCallView.swift")
    assert "app.relationship.title" in voice
    assert "app.performanceMode.isPublic" in voice
    assert "Voice unavailable · text still works" in voice
    assert "tap the mic" in voice


def test_product_uses_existing_approved_mary_art_and_system_symbols_only():
    together = _text("TogetherView.swift")
    home = _text("HomeView.swift")
    assert "MaryArtwork(asset: .manga" in together
    assert "MaryArtwork(asset: .streamRoom" in home
    assert "http://" not in together
    assert "https://" not in together
    assert "http://" not in home
    assert "https://" not in home


def test_native_release_metadata_advances_for_product_pass():
    plist = (IOS / "Info.plist").read_text(encoding="utf-8")
    assert "<key>CFBundleShortVersionString</key><string>0.5</string>" in plist
    assert "<key>CFBundleVersion</key><string>5</string>" in plist


def test_existing_touch_accessibility_contract_still_applies():
    theme = _text("Theme.swift")
    assert "minimumTouchTarget: CGFloat = 44" in theme
    assert "accessibilityReduceMotion" in theme
