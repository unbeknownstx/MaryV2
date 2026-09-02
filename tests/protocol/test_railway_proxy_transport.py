from __future__ import annotations

import sys
from types import SimpleNamespace

from mary.protocol import server


def _capture_uvicorn(monkeypatch):
    captured = {}

    def run(app, **kwargs):
        captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=run))
    monkeypatch.setattr(server, "create_app", lambda: object())
    monkeypatch.setenv("MARY_CORE_TOKEN", "test-token")
    monkeypatch.setenv("MARY_CORE_HOST", "127.0.0.1")
    monkeypatch.setenv("MARY_CORE_PORT", "8080")
    return captured


def test_run_server_trusts_railway_edge_proxy_headers(monkeypatch):
    captured = _capture_uvicorn(monkeypatch)
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "mary-core")

    server.run_server()

    assert captured["proxy_headers"] is True
    assert captured["forwarded_allow_ips"] == "*"


def test_run_server_keeps_restrictive_proxy_default_off_railway(monkeypatch):
    captured = _capture_uvicorn(monkeypatch)
    for name in ("RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("MARY_CORE_FORWARDED_ALLOW_IPS", raising=False)

    server.run_server()

    assert captured["proxy_headers"] is True
    assert captured["forwarded_allow_ips"] == "127.0.0.1"


def test_non_railway_proxy_allowlist_can_be_explicitly_configured(monkeypatch):
    captured = _capture_uvicorn(monkeypatch)
    for name in ("RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MARY_CORE_FORWARDED_ALLOW_IPS", "10.0.0.5")

    server.run_server()

    assert captured["forwarded_allow_ips"] == "10.0.0.5"
