from __future__ import annotations

import io
import json

import scripts.enroll_capability_node as module


class _Response:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def test_issue_grant_posts_creator_auth_without_printing_grant(monkeypatch):
    observed = {}

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["authorization"] = request.headers.get("Authorization")
        observed["body"] = json.loads(request.data.decode("utf-8"))
        observed["timeout"] = timeout
        return _Response({"enrollment_grant": "secret-test-one-time-grant"})

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    grant = module._issue_grant(
        core_url="https://mary.example",
        creator_token="secret-test-creator",
        node_id="mac-node",
    )
    assert grant == "secret-test-one-time-grant"
    assert observed == {
        "url": "https://mary.example/v1/nodes/enrollment-grants",
        "authorization": "Bearer secret-test-creator",
        "body": {
            "node_id": "mac-node",
            "expires_in_seconds": 300,
            "max_uses": 1,
        },
        "timeout": 15,
    }


def test_main_passes_grant_but_not_creator_token_to_node_child(monkeypatch, capsys):
    monkeypatch.setattr(module, "load_dotenv", lambda *_args, **_kwargs: True)
    monkeypatch.setenv("MARY_CORE_URL", "https://mary.example")
    monkeypatch.setenv("MARY_CORE_TOKEN", "secret-test-creator")
    monkeypatch.setenv("MARY_NODE_ID", "mac-node")
    monkeypatch.setenv("MARY_LLAMA_CPP_ENABLED", "true")
    monkeypatch.setattr(module, "_issue_grant", lambda **_kwargs: "secret-test-one-time")
    observed = {}

    class Completed:
        returncode = 0

    def fake_run(command, *, env, check):
        observed["command"] = command
        observed["grant"] = env.get("MARY_NODE_ENROLLMENT_GRANT")
        observed["creator"] = env.get("MARY_CORE_TOKEN")
        observed["llama"] = env.get("MARY_LLAMA_CPP_ENABLED")
        observed["check"] = check
        return Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    assert module.main([]) == 0
    assert observed["command"][-3:] == ["-m", "scripts.run_capability_node", "--enroll-only"]
    assert observed["grant"] == "secret-test-one-time"
    assert observed["creator"] == ""
    assert observed["llama"] == "true"
    assert observed["check"] is False
    output = capsys.readouterr().out
    assert "secret-test-one-time" not in output
    assert "secret-test-creator" not in output
    assert "not displayed" in output


def test_main_requires_creator_configuration(monkeypatch):
    monkeypatch.setattr(module, "load_dotenv", lambda *_args, **_kwargs: True)
    monkeypatch.delenv("MARY_CORE_URL", raising=False)
    monkeypatch.delenv("MARY_CORE_TOKEN", raising=False)
    assert module.main([]) == 2
