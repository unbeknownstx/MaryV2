from __future__ import annotations

from http.client import HTTPConnection
from threading import Thread
import json

from mary.mobile.server import MaryMobileServer, MobileAuth


class _Runtime:
    def status(self):
        return {"name": "Mary"}

    def dashboard_state(self):
        return {
            "core": {"architecture": "13.2", "ok": True},
            "live": {
                "character": {
                    "name": "Mary",
                    "status": "thinking",
                    "mood": "neutral",
                    "energy": "engaged",
                    "memory_count": 23,
                }
            },
            "relationship": {"score": 72, "label": "Established"},
        }

    def last_turn_trace(self):
        return {"provider": "groq", "model": "openai/gpt-oss-20b", "lane": "social_instant"}

    def close(self):
        pass


def _serve(tmp_path):
    (tmp_path / "index.html").write_text("<html>Mary</html>", encoding="utf-8")
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=_Runtime(),
        static_root=tmp_path,
        auth=MobileAuth("secret", "test", None),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    return server, thread


def test_experience_endpoint_is_authenticated_and_presentation_only(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        conn.request("GET", "/api/experience")
        unauthorized = conn.getresponse()
        unauthorized.read()
        assert unauthorized.status == 401

        conn.request("GET", "/api/experience", headers={"Authorization": "Bearer secret"})
        response = conn.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200
        assert payload["ok"] is True
        assert payload["authority"] == "presentation_projection_only"
        assert payload["identity_owner"] == "mary_core"
        assert payload["interaction_state"] == "thinking"
        assert payload["relationship_strength"] == 0.72
        assert payload["memory_count"] == 23
        assert payload["provider"] == "groq"
        assert payload["provider"] != payload["identity_owner"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
