from __future__ import annotations

from mary.voice import SpeechRenderer


def test_speech_renderer_keeps_meaning_but_removes_markdown_noise() -> None:
    renderer = SpeechRenderer()
    source = """## About me\n- I'm **MaryV2**.\n- See [the guide](https://example.com/guide).\n"""
    spoken = renderer.render(source)
    assert "Mary V two" in spoken
    assert "**" not in spoken
    assert "##" not in spoken
    assert "https://" not in spoken
    assert "the guide" in spoken


def test_speech_renderer_does_not_read_fenced_code_body() -> None:
    renderer = SpeechRenderer()
    spoken = renderer.render("Try this:\n```python\nprint('secret')\n```\nThen continue.")
    assert "print" not in spoken
    assert "I included the code in the text response." in spoken
    assert "Then continue." in spoken


def test_speech_renderer_is_local_and_deterministic() -> None:
    renderer = SpeechRenderer()
    text = "MaryV2 is ready."
    assert renderer.render(text) == renderer.render(text) == "Mary V two is ready."
