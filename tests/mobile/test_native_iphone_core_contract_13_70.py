from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IOS = ROOT / "ios" / "MaryV2iOS" / "Sources"


def _text(name: str) -> str:
    return (IOS / name).read_text(encoding="utf-8")


def test_native_iphone_client_uses_canonical_core_contract() -> None:
    client = _text("MaryCoreClient.swift")

    for route in (
        "/v1/health",
        "/v1/state",
        "/v1/dashboard",
        "/v1/workspace",
        "/v1/memory/status",
        "/v1/nodes",
        "/v1/voice/status",
        "/v1/turn",
        "/v1/voice/synthesize",
        "/v1/workspace/action",
        "/v1/nodes/task/dispatch",
        "/v1/creator-surfaces/register",
        "/v1/creator-surfaces/renew",
        "/v1/creator-surfaces/visibility",
        "/v1/creator-surfaces/wake",
        "/v1/creator-surfaces/disconnect",
    ):
        assert route in client

    assert '"surface": "ios_native"' in client
    assert '"device_id": deviceID' in client
    assert '"conversation_id": conversationID' in client


def test_native_iphone_state_routes_turns_work_and_voice_through_core() -> None:
    state = _text("AppState.swift")

    assert "client.turn(" in state
    assert "client.workspace()" in state
    assert "client.workspaceAction(action, args: args)" in state
    assert "client.synthesizeVoice(" in state
    assert "client.voiceStatus()" in state


def test_native_iphone_work_surface_mutates_canonical_projects_and_tasks() -> None:
    work = _text("WorkFocusViews.swift")

    for action in ("project.create", "task.create", "task.update", "task.complete"):
        assert f'"{action}"' in work
    assert "app.runWorkspaceAction(" in work


def test_native_iphone_voice_has_local_input_and_core_output_paths() -> None:
    capture = _text("VoiceCapture.swift")
    playback = _text("VoicePlayback.swift")
    call = _text("VoiceCallView.swift")

    assert "requiresOnDeviceRecognition = true" in capture
    assert "SFSpeechURLRecognitionRequest" in capture
    assert "AVAudioPlayer(data: audio.data)" in playback
    assert "AVSpeechSynthesizer" in playback
    assert "speakDevice" in playback
    assert "voiceServerAvailable" in call
    assert "Core voice unavailable · iPhone voice fallback ready" in call
