from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread

from mary.mobile.server import (
    MaryMobileServer,
    MobileAuth,
    _missing_static_assets,
)


class _Runtime:
    def status(self):
        return {"name": "Mary"}

    def close(self):
        pass


def _serve(
    static_root: Path,
    *,
    token: str = "",
):
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=_Runtime(),
        static_root=static_root,
        auth=MobileAuth(
            token,
            "test" if token else "loopback",
            None,
        ),
    )
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    return server, thread


def test_replit_identity_headers_never_replace_mobile_bearer(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html>Mary</html>",
        encoding="utf-8",
    )
    server, thread = _serve(
        tmp_path,
        token="test-token",
    )
    headers = {
        "Host": "workspace-id.mobile.replit.dev",
        "Origin": "https://workspace-id.mobile.replit.dev",
        "Sec-Fetch-Site": "same-origin",
        "X-Replit-User-Id": "12345678",
    }
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "GET",
            "/api/health",
            headers=headers,
        )
        health = conn.getresponse()
        health.read()

        conn.request(
            "POST",
            "/api/auth/preview",
            body=b"{}",
            headers={
                **headers,
                "Content-Type": "application/json",
            },
        )
        bootstrap = conn.getresponse()
        bootstrap.read()

        assert health.status == 401
        assert bootstrap.status == 401
        assert bootstrap.getheader("Set-Cookie") is None
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
    server, thread = _serve(tmp_path)
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
    (tmp_path / "index.html").write_text(
        '<link rel="icon" href="./assets/mary-icon.png">',
        encoding="utf-8",
    )
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


def test_spa_fallback_and_unknown_api_404_remain_distinct(tmp_path):
    shell = b"<html>Mary shell</html>"
    (tmp_path / "index.html").write_bytes(shell)
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "GET",
            "/conversations/demo",
        )
        route = conn.getresponse()
        route_body = route.read()

        conn.request(
            "GET",
            "/api/definitely-unknown",
        )
        unknown = conn.getresponse()
        unknown_payload = json.loads(
            unknown.read()
        )

        assert route.status == 200
        assert route_body == shell
        assert unknown.status == 404
        assert unknown_payload["error"] == "Unknown API route."
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


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