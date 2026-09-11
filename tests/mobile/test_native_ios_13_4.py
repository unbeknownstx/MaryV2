from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IOS = ROOT / "ios" / "MaryV2iOS"


def _text(name: str) -> str:
    return (IOS / "Sources" / name).read_text(encoding="utf-8")


def test_native_ios_is_a_direct_core_surface_not_a_webview_wrapper():
    client = _text("MaryCoreClient.swift")
    root = _text("RootView.swift")
    assert '"surface": "ios_native"' in client
    assert '"/v1/turn"' in client
    assert "WKWebView" not in root
    assert "mobile_web" not in root


def test_native_ios_voice_keeps_raw_microphone_local_and_uses_core_tts():
    client = _text("MaryCoreClient.swift")
    capture = _text("VoiceCapture.swift")
    playback = _text("VoicePlayback.swift")

    assert '"/v1/voice/synthesize"' in client
    assert '"/v1/voice/transcribe"' not in client
    assert "SFSpeechURLRecognitionRequest" in capture
    assert "requiresOnDeviceRecognition = true" in capture
    assert "FileManager.default.removeItem" in capture
    assert "AVAudioPlayer" in playback


def test_native_ios_contains_no_provider_credentials_or_provider_key_names():
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in IOS.rglob("*")
        if path.is_file() and path.suffix in {".swift", ".plist", ".yml"}
    )
    for forbidden in (
        "ELEVENLABS_API_KEY",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
    ):
        assert forbidden not in combined


def test_native_ios_core_credential_uses_keychain_device_only_accessibility():
    keychain = _text("KeychainStore.swift")
    assert "kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly" in keychain
    assert "kSecClassGenericPassword" in keychain
