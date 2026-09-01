from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread

from mary.mobile.server import (
    MaryMobileServer,
    MobileAuth,
    MobilePreviewAuth,
    MobilePreviewSessions,
    _missing_static_assets,
    _resolve_preview_auth,
)


PREVIEW_HOST = "workspace-id.mobile.replit.dev"
OWNER_ID = "12345678"


class _Runtime:
    def status(self):
        return {"name": "Mary"}

    def close(self):
        pass

    def surface_register(
        self,
        *,
        surface_id,
        visible,
        foreground,
        lease_seconds,
    ):
        return {
            "surface_id": surface_id,
            "visible": visible,
            "foreground": foreground,
            "lease_seconds": lease_seconds,
        }


def _preview_config(*, ttl: int = 300) -> MobilePreviewAuth:
    return MobilePreviewAuth(
        enabled=True,
        expected_host=PREVIEW_HOST,
        allowed_user_ids=frozenset({OWNER_ID}),
        session_ttl_seconds=ttl,
    )


def _serve(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<html>Mary</html>",
        encoding="utf-8",
    )
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=_Runtime(),
        static_root=tmp_path,
        auth=MobileAuth("mobile-edge-secret", "test", None),
        preview_auth=_preview_config(),
    )
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    return server, thread


def _preview_headers(**overrides):
    headers = {
        "Host": PREVIEW_HOST,
        "Origin": f"https://{PREVIEW_HOST}",
        "Sec-Fetch-Site": "same-origin",
        "X-Replit-User-Id": OWNER_ID,
        "Content-Type": "application/json",
    }
    headers.update(overrides)
    return headers


def test_preview_auth_is_explicit_replit_owner_scoped_and_fail_closed(
    monkeypatch,
):
    for name in (
        "MARY_MOBILE_REPLIT_PREVIEW_BOOTSTRAP",
        "MARY_MOBILE_PREVIEW_USER_IDS",
        "MARY_MOBILE_PREVIEW_SESSION_TTL_SECONDS",
        "REPL_ID",
        "REPLIT_DEV_DOMAIN",
        "REPL_OWNER_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    assert _resolve_preview_auth().enabled is False

    monkeypatch.setenv("MARY_MOBILE_REPLIT_PREVIEW_BOOTSTRAP", "1")
    monkeypatch.setenv("REPL_ID", "workspace")
    monkeypatch.setenv("REPLIT_DEV_DOMAIN", PREVIEW_HOST)
    monkeypatch.setenv("REPL_OWNER_ID", OWNER_ID)
    resolved = _resolve_preview_auth()

    assert resolved.enabled is True
    assert resolved.expected_host == PREVIEW_HOST
    assert resolved.allowed_user_ids == frozenset({OWNER_ID})
    assert resolved.session_ttl_seconds == 300

    monkeypatch.setenv("REPLIT_DEV_DOMAIN", "attacker.example")
    assert _resolve_preview_auth().enabled is False


def test_preview_session_expires_and_is_bound_to_user_and_audience():
    now = [100.0]
    sessions = MobilePreviewSessions(
        _preview_config(ttl=60),
        clock=lambda: now[0],
    )
    token, ttl = sessions.issue(
        user_id=OWNER_ID,
        audience=PREVIEW_HOST,
    )

    assert ttl == 60
    assert sessions.authorized(
        token,
        user_id=OWNER_ID,
        audience=PREVIEW_HOST,
    )
    assert not sessions.authorized(
        token,
        user_id="other-user",
        audience=PREVIEW_HOST,
    )
    assert not sessions.authorized(
        token,
        user_id=OWNER_ID,
        audience="other.replit.dev",
    )

    now[0] = 161.0
    assert not sessions.authorized(
        token,
        user_id=OWNER_ID,
        audience=PREVIEW_HOST,
    )


def test_authorized_preview_mints_httponly_session_without_edge_secret(
    tmp_path,
):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "POST",
            "/api/auth/preview",
            body=b"{}",
            headers=_preview_headers(),
        )
        response = conn.getresponse()
        raw = response.read()
        payload = json.loads(raw)
        cookie = response.getheader("Set-Cookie")

        assert response.status == 200
        assert payload == {
            "ok": True,
            "auth": "replit_preview_session",
            "expires_in_seconds": 300,
        }
        assert "mobile-edge-secret" not in raw.decode("utf-8")
        assert cookie
        assert cookie.startswith("__Host-mary-mobile-preview=")
        assert "Path=/" in cookie
        assert "Max-Age=300" in cookie
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie

        session_cookie = cookie.split(";", 1)[0]
        conn.request(
            "GET",
            "/api/health",
            headers={
                "Host": PREVIEW_HOST,
                "X-Replit-User-Id": OWNER_ID,
                "Cookie": session_cookie,
            },
        )
        health = conn.getresponse()
        health_payload = json.loads(health.read())
        assert health.status == 200
        assert health_payload["ok"] is True

        conn.request(
            "POST",
            "/api/lifecycle/register",
            body=json.dumps(
                {
                    "surface_id": "test-preview",
                    "visible": True,
                    "foreground": True,
                }
            ),
            headers={
                **_preview_headers(),
                "Cookie": session_cookie,
            },
        )
        registered = conn.getresponse()
        registered_payload = json.loads(registered.read())
        assert registered.status == 200
        assert (
            registered_payload["lifecycle"]["surface_id"]
            == "test-preview"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_preview_bootstrap_rejects_wrong_user_origin_and_host(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        rejected = (
            {"X-Replit-User-Id": "other-user"},
            {"Origin": "https://attacker.example"},
            {"Host": "other.replit.dev"},
            {"Sec-Fetch-Site": "cross-site"},
        )
        for override in rejected:
            conn.request(
                "POST",
                "/api/auth/preview",
                body=b"{}",
                headers=_preview_headers(**override),
            )
            response = conn.getresponse()
            response.read()
            assert response.status == 401
            assert response.getheader("Set-Cookie") is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bearer_client_remains_authenticated_without_preview_headers(
    tmp_path,
):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "GET",
            "/api/health",
            headers={
                "Authorization": "Bearer mobile-edge-secret",
            },
        )
        accepted = conn.getresponse()
        accepted.read()
        assert accepted.status == 200

        conn.request(
            "GET",
            "/api/health",
        )
        rejected = conn.getresponse()
        rejected.read()
        assert rejected.status == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_incomplete_shell_reproduces_asset_404_and_is_detected_at_startup(
    tmp_path,
):
    (tmp_path / "index.html").write_text(
        '<script src="./missing-app.js"></script>',
        encoding="utf-8",
    )
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=_Runtime(),
        static_root=tmp_path,
        auth=MobileAuth("", "loopback", None),
    )
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "GET",
            "/missing-app.js",
        )
        missing = conn.getresponse()
        missing.read()
        assert missing.status == 404
        assert _missing_static_assets(tmp_path) == [
            "missing-app.js",
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_conventional_favicon_path_maps_to_existing_mobile_icon(tmp_path):
    icon = b"\x89PNG\r\nMary"
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "mary-icon.png").write_bytes(icon)
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "GET",
            "/favicon.ico",
        )
        response = conn.getresponse()
        raw = response.read()

        assert response.status == 200
        assert raw == icon
        assert response.getheader("Content-Type") == "image/png"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mobile_browser_bootstrap_never_names_server_credentials():
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "mobile_web"
        / "app.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "/api/auth/preview" in source
    assert "credentials:'same-origin'" in source
    assert "MARY_MOBILE_TOKEN" not in source
    assert "MARY_CORE_TOKEN" not in source


def test_mobile_server_never_logs_generated_bearer_value():
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "mary"
        / "mobile"
        / "server.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "print(\n                auth.token," not in source
    assert "not written to logs" in source
