from __future__ import annotations

import base64
from pathlib import Path

from mary.desktop.audio_cache import DesktopAudioCache


def test_audio_cache_stages_base64_as_local_file_url_and_cleans_up(tmp_path):
    cache = DesktopAudioCache(tmp_path / "voice", max_files=4)
    raw = b"ID3" + (b"x" * 64)
    payload = cache.stage({
        "enabled": True,
        "status": "success",
        "format": "mp3",
        "mime_type": "audio/mpeg",
        "audio_base64": base64.b64encode(raw).decode("ascii"),
    })
    assert payload["audio_transport"] == "file_url"
    assert payload["audio_url"].startswith("file:")
    assert "audio_base64" not in payload
    files = list((tmp_path / "voice").glob("*.mp3"))
    assert len(files) == 1
    assert files[0].read_bytes() == raw
    cache.cleanup()
    assert not list((tmp_path / "voice").glob("*.mp3"))


def test_frontend_prefers_file_transport_and_reports_startup_stages():
    source = Path("desktop/src/main.js").read_text(encoding="utf-8")
    assert "voice.audio_url" in source
    assert "voicePlaybackStage?.('payload_received')" in source
    assert "voicePlaybackStage?.('audio_ready')" in source
    assert "voicePlaybackStage?.('play_requested')" in source
    assert "addEventListener('playing'" in source
    # Lip sync must not be attached before play() anymore.
    play_block = source[source.index("function playVoice(voice = {})"):source.index("function configuredAmbientVolume()")]
    assert play_block.index("audio.play()") < play_block.index("attachLipSyncToAudio(audio)") or "addEventListener('playing'" in play_block


def test_qt_webview_allows_local_temp_audio_file_urls():
    source = Path("mary/desktop/window.py").read_text(encoding="utf-8")
    assert "LocalContentCanAccessFileUrls" in source
    assert "True" in source[source.index("LocalContentCanAccessFileUrls"):source.index("PlaybackRequiresUserGesture")]
