from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_stream_cohost_runner_uses_canonical_core_and_public_projection() -> None:
    source = _text("scripts/run_stream_cohost.py")
    assert "MaryClient(" in source
    assert 'surface="stream_cohost"' in source
    assert '"performance.context.set"' in source
    assert '"mode": "stream"' in source
    assert '"stream.chat.ingest"' in source
    assert "client.turn" in source
    assert '"/v1/voice/synthesize"' in source
    assert "LocalOBSRelay" in source
    assert "create_application" not in source
    assert "MaryApplication(" not in source


def test_stream_cohost_keeps_credentials_out_of_obs_browser_relay() -> None:
    relay = _text("mary/streaming/relay.py")
    assert 'normalized_host not in {"127.0.0.1", "localhost", "::1"}' in relay
    assert "Mary stream relay is loopback-only" in relay
    assert "MARY_CORE_TOKEN" not in relay
    assert "MARY_TWITCH_OAUTH_TOKEN" not in relay
    assert "Authorization" not in relay


def test_stream_cohost_documents_optional_avatar_and_perception_boundary() -> None:
    doc = _text("docs/architecture/STREAM_COHOST_13_10.md")
    assert "canonical Mary Core" in doc
    assert "Live2D" in doc
    assert "2.5D" in doc
    assert "3D" in doc
    assert "perception.observe" in doc
    assert "untrusted social context" in doc
    assert "does not yet provide final Live2D/2.5D/3D rendering" in doc


def test_streaming_dependencies_remain_optional() -> None:
    requirements = _text("requirements-streaming.txt")
    base_requirements = _text("requirements.txt")
    assert "websockets" in requirements
    assert "websockets" not in base_requirements
