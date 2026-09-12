from __future__ import annotations

from mary.streaming.creator_audio import StreamCreatorMicrophone


def test_stream_creator_microphone_builds_valid_wav() -> None:
    pcm = (b"\x00\x00" * 1600)
    wav = StreamCreatorMicrophone._wav_bytes(pcm)
    assert wav.startswith(b"RIFF")
    assert b"WAVE" in wav[:16]
    assert len(wav) > len(pcm)


def test_stream_creator_voice_runner_preserves_public_lane_contract() -> None:
    source = open("scripts/run_stream_creator_voice.py", "r", encoding="utf-8").read()
    assert 'MARY_STREAM_CONVERSATION_ID", "stream-public"' in source
    assert '"sensor.audio_transcribe"' in source
    assert 'voice_input=True' in source
    assert 'MARY_STREAM_CREATOR_HEARING' in source
    assert 'realtime.voice_activity' in source
    assert 'relationship' not in source.casefold()
    assert 'memory' not in source.casefold()
