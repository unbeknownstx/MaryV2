from mary.desktop.stt import DesktopSpeechToText


def test_whisper_cpp_backend_is_optional_and_local(monkeypatch, tmp_path):
    executable = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-base.en.bin"
    executable.write_text("placeholder", encoding="utf-8")
    model.write_bytes(b"model")
    monkeypatch.setenv("MARY_WHISPER_CPP_EXECUTABLE", str(executable))
    monkeypatch.setenv("MARY_WHISPER_CPP_MODEL", str(model))
    stt = DesktopSpeechToText(provider="whisper_cpp", model="ignored", language="en", api_key=None)
    assert stt.enabled is True
    assert stt.status.provider == "whisper_cpp"
    assert stt.status.local is True
