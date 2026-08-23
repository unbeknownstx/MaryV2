from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
import json
import urllib.error
import urllib.request

import pytest

from scripts.benchmark_qwen_micro_cortex import (
    BenchmarkOptions,
    DEFAULT_BASE_URL,
    OllamaHTTPClient,
)


def _ndjson(*chunks: object) -> list[bytes]:
    return [
        (json.dumps(chunk, ensure_ascii=False) + "\n").encode("utf-8")
        for chunk in chunks
    ]


class _FakeResponse:
    def __init__(
        self,
        *,
        lines: Iterable[bytes] = (),
        body: bytes = b"",
    ) -> None:
        self._lines = list(lines)
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)

    def read(self) -> bytes:
        return self._body


class _FakeOpener:
    def __init__(self, *outcomes: object) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[tuple[urllib.request.Request, float]] = []

    def open(self, request: urllib.request.Request, *, timeout: float):
        self.requests.append((request, timeout))
        if not self._outcomes:
            raise AssertionError("unexpected HTTP request")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _SequenceClock:
    def __init__(self, *milliseconds: float) -> None:
        self._values = iter(int(value * 1_000_000) for value in milliseconds)

    def __call__(self) -> int:
        try:
            return next(self._values)
        except StopIteration as exc:
            raise AssertionError("benchmark requested more clock samples than expected") from exc


class _TickClock:
    def __init__(self) -> None:
        self._value = 0

    def __call__(self) -> int:
        value = self._value
        self._value += 1_000_000
        return value


def test_default_endpoint_is_explicit_ipv4_loopback_without_proxy_lookup(monkeypatch):
    assert DEFAULT_BASE_URL == "http://127.0.0.1:11434"

    captured_handlers: list[object] = []
    opener = _FakeOpener()

    def _capture_build_opener(*handlers: object):
        captured_handlers.extend(handlers)
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", _capture_build_opener)
    client = OllamaHTTPClient()
    assert client.base_url == DEFAULT_BASE_URL
    assert client.sanitized_base_url == DEFAULT_BASE_URL

    proxy_handlers = [handler for handler in captured_handlers if isinstance(handler, urllib.request.ProxyHandler)]
    assert len(proxy_handlers) == 1
    assert proxy_handlers[0].proxies == {}


@pytest.mark.parametrize(
    ("base_url", "expected"),
    (
        (
            "https://alice:p%40ss@localhost:11434/ollama/?token=private#fragment",
            "https://localhost:11434/ollama",
        ),
        ("http://bob:private@[::1]:11434", "http://[::1]:11434"),
    ),
)
def test_endpoint_metadata_strips_userinfo_query_and_fragment(base_url: str, expected: str):
    client = OllamaHTTPClient(base_url=base_url, opener=_FakeOpener())
    assert client.sanitized_base_url == expected
    assert "alice" not in client.sanitized_base_url
    assert "private" not in client.sanitized_base_url
    assert "token" not in client.sanitized_base_url


@pytest.mark.parametrize(
    "base_url",
    ("localhost:11434", "ftp://127.0.0.1:11434", "http:///missing-host"),
)
def test_endpoint_rejects_non_http_or_relative_urls(base_url: str):
    with pytest.raises(ValueError, match=r"absolute http\(s\) URL"):
        OllamaHTTPClient(base_url=base_url)


def test_url_error_uses_only_sanitized_endpoint_metadata():
    opener = _FakeOpener(urllib.error.URLError("connection refused"))
    client = OllamaHTTPClient(
        base_url="http://alice:secret@127.0.0.1:11434",
        opener=opener,
    )

    with pytest.raises(RuntimeError) as captured:
        client.version()

    message = str(captured.value)
    assert "http://127.0.0.1:11434" in message
    assert "alice" not in message
    assert "secret" not in message


def test_buffered_json_records_client_transport_timing():
    opener = _FakeOpener(
        _FakeResponse(body=b'{"version":"test-ollama"}')
    )
    client = OllamaHTTPClient(
        opener=opener,
        clock_ns=_SequenceClock(0, 2, 5, 6),
    )

    result = client.version()

    assert result["version"] == "test-ollama"
    assert result["_client_wall_ms"] == 6.0
    assert result["_http_headers_ms"] == 2.0
    assert result["_http_body_ms"] == 3.0
    assert result["_transport"] == "ollama_json"
    request, timeout = opener.requests[0]
    assert request.full_url == "http://127.0.0.1:11434/api/version"
    assert request.get_method() == "GET"
    assert timeout == 120.0


def test_stream_reassembles_unicode_thinking_tools_and_first_content_timing():
    tool_call = {
        "function": {
            "name": "synthetic_tool",
            "arguments": {"value": "kept"},
        }
    }
    lines = _ndjson(
        {"message": {"thinking": "hmm"}, "done": False},
        {"message": {"content": "   "}, "done": False},
        {"message": {"content": "Hi "}, "done": False},
        {
            "message": {"content": "👋\nthere", "tool_calls": [tool_call]},
            "done": False,
        },
        {
            "message": {"content": "", "thinking": ""},
            "done": True,
            "done_reason": "stop",
            "total_duration": 9_000_000,
            "load_duration": 1_000_000,
            "prompt_eval_duration": 2_000_000,
            "eval_duration": 5_000_000,
            "prompt_eval_count": 20,
            "eval_count": 4,
        },
    )
    opener = _FakeOpener(_FakeResponse(lines=lines))
    client = OllamaHTTPClient(
        opener=opener,
        clock_ns=_SequenceClock(0, 1, 3, 4, 6, 8, 10, 12),
    )

    result = client.chat(
        model="qwen3:1.7b",
        messages=({"role": "user", "content": "Speak briefly."},),
        options=BenchmarkOptions(stream=True),
    )

    assert result["done"] is True
    assert result["done_reason"] == "stop"
    assert result["message"] == {
        "content": "   Hi 👋\nthere",
        "thinking": "hmm",
        "tool_calls": [tool_call],
    }
    assert result["_client_wall_ms"] == 12.0
    assert result["_http_headers_ms"] == 1.0
    assert result["_first_chunk_ms"] == 3.0
    assert result["_first_thinking_ms"] == 3.0
    assert result["_first_content_ms"] == 6.0
    assert result["_http_body_ms"] == 11.0
    assert result["_ndjson_chunks"] == 5
    assert result["_transport"] == "ollama_ndjson_stream"
    assert result["total_duration"] == 9_000_000

    request, _ = opener.requests[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["stream"] is True
    assert payload["think"] is False
    assert payload["keep_alive"] == "10m"
    assert payload["options"]["num_ctx"] == 1024
    assert payload["options"]["num_predict"] == 48


@pytest.mark.parametrize(
    ("lines", "message"),
    (
        ([b"{not-json}\n"], "invalid NDJSON"),
        (_ndjson({"error": "synthetic failure"}), "stream error: synthetic failure"),
        (_ndjson({"message": {"content": "partial"}, "done": False}), "before done=true"),
    ),
)
def test_stream_protocol_errors_are_explicit(lines: list[bytes], message: str):
    client = OllamaHTTPClient(
        opener=_FakeOpener(_FakeResponse(lines=lines)),
        clock_ns=_TickClock(),
    )

    with pytest.raises(RuntimeError, match=message):
        client.chat(
            model="qwen3:1.7b",
            messages=({"role": "user", "content": "test"},),
            options=BenchmarkOptions(stream=True),
        )


def test_http_error_body_is_bounded_and_does_not_expose_endpoint_credentials():
    error = urllib.error.HTTPError(
        url="http://127.0.0.1:11434/api/chat",
        code=503,
        msg="Unavailable",
        hdrs=None,
        fp=BytesIO(b"x" * 900),
    )
    client = OllamaHTTPClient(
        base_url="http://alice:secret@127.0.0.1:11434",
        opener=_FakeOpener(error),
        clock_ns=_TickClock(),
    )

    with pytest.raises(RuntimeError) as captured:
        client.version()

    message = str(captured.value)
    assert message.startswith("Ollama HTTP 503: ")
    assert len(message.removeprefix("Ollama HTTP 503: ")) == 600
    assert "alice" not in message
    assert "secret" not in message


def test_stream_rejects_non_object_chunks_as_protocol_errors():
    client = OllamaHTTPClient(
        opener=_FakeOpener(_FakeResponse(lines=_ndjson(["not", "an", "object"]))),
        clock_ns=_TickClock(),
    )

    with pytest.raises(RuntimeError, match="JSON object"):
        client.chat(
            model="qwen3:1.7b",
            messages=({"role": "user", "content": "test"},),
            options=BenchmarkOptions(stream=True),
        )


def test_stream_rejects_chunks_after_terminal_done():
    client = OllamaHTTPClient(
        opener=_FakeOpener(
            _FakeResponse(
                lines=_ndjson(
                    {"message": {"content": "final"}, "done": True},
                    {"message": {"content": "unexpected trailing text"}, "done": False},
                )
            )
        ),
        clock_ns=_TickClock(),
    )

    with pytest.raises(RuntimeError, match="after done=true"):
        client.chat(
            model="qwen3:1.7b",
            messages=({"role": "user", "content": "test"},),
            options=BenchmarkOptions(stream=True),
        )


def test_stream_wraps_invalid_utf8_as_a_protocol_error():
    client = OllamaHTTPClient(
        opener=_FakeOpener(_FakeResponse(lines=[b"\xff\xfe\n"])),
        clock_ns=_TickClock(),
    )

    with pytest.raises(RuntimeError, match="UTF-8"):
        client.chat(
            model="qwen3:1.7b",
            messages=({"role": "user", "content": "test"},),
            options=BenchmarkOptions(stream=True),
        )
