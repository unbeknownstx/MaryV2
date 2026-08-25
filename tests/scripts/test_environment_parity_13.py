from scripts.check_environment_parity import snapshot


def test_environment_parity_snapshot_is_display_safe(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret-groq")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-eleven")
    monkeypatch.setenv("MARY_GROQ_MODEL", "openai/gpt-oss-20b")
    result = snapshot()
    rendered = repr(result)
    assert result["mary_version"] in {"13.0.0", "13.1.1"}
    assert result["models"]["groq"] == "openai/gpt-oss-20b"
    assert "secret-groq" not in rendered
    assert "secret-eleven" not in rendered
