from __future__ import annotations

from http.client import HTTPConnection
from threading import RLock, Thread
from types import SimpleNamespace
import json

import mary.mobile.server as mobile_server
from mary.mobile.server import MaryMobileRuntime, MaryMobileServer, MobileAuth


class _Runtime:
    trace_queries = []

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
            "character_sourcebook": {
                "records": 189,
                "source_names": ["PRIVATE_AUTHORED_SOURCE"],
                "records_preview": ["PRIVATE_AUTHORED_EVIDENCE"],
            },
        }

    def last_turn_trace(self):
        return {"provider": "groq", "model": "openai/gpt-oss-20b", "lane": "social_instant"}

    def query_turn_traces(self, **query):
        self.trace_queries.append(query)
        return {
            "traces": [{"request_id": query.get("request_id"), "core_instance_id": "core-1"}],
            "count": 1,
        }

    def close(self):
        pass


def _serve(tmp_path, runtime=None):
    (tmp_path / "index.html").write_text("<html>Mary</html>", encoding="utf-8")
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=runtime or _Runtime(),
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
        assert payload["metadata"]["character_records"] == 189
        assert "PRIVATE_AUTHORED_SOURCE" not in repr(payload)
        assert "PRIVATE_AUTHORED_EVIDENCE" not in repr(payload)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_trace_query_endpoint_is_authenticated_and_bounded(tmp_path):
    runtime = _Runtime()
    runtime.trace_queries = []
    server, thread = _serve(tmp_path, runtime=runtime)
    try:
        conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        conn.request("GET", "/api/traces?request_id=request-safe&limit=999")
        unauthorized = conn.getresponse()
        unauthorized.read()
        assert unauthorized.status == 401

        conn.request(
            "GET",
            "/api/traces?request_id=request-safe&limit=999",
            headers={"Authorization": "Bearer secret"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200
        assert payload["traces"][0]["request_id"] == "request-safe"
        assert runtime.trace_queries == [{
            "request_id": "request-safe",
            "turn_id": "",
            "limit": 40,
        }]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_local_mobile_runtime_projects_real_sourcebook_count_only(
    monkeypatch,
    tmp_path,
):
    class _Status:
        def status(self):
            return {}

        def snapshot(self):
            return {}

    sourcebook = SimpleNamespace(
        snapshot=lambda: {
            "version": "13.2",
            "records": 189,
            "sourcebook_hash": "abcdef1234567890abcd",
            "errors": ["PRIVATE_SOURCE_PATH"],
            "source_names": ["PRIVATE_AUTHORED_SOURCE"],
            "records_preview": ["PRIVATE_AUTHORED_EVIDENCE"],
        }
    )
    mary = SimpleNamespace(
        character_sourcebook=sourcebook,
        mind=SimpleNamespace(
            status=lambda: {},
            retrieval=_Status(),
        ),
        engagement=_Status(),
        growth=_Status(),
        realtime=_Status(),
        node_registry=_Status(),
        perception_director=_Status(),
        training_feedback=_Status(),
    )
    runtime = object.__new__(MaryMobileRuntime)
    runtime._lock = RLock()
    runtime._busy = False
    runtime._conversation_id = "local-test"
    runtime._last_trace = {}
    runtime.application = SimpleNamespace(
        mary=mary,
        close=lambda: None,
    )
    runtime.ecosystem = SimpleNamespace(
        snapshot=lambda: {},
        metrics=SimpleNamespace(
            last_turn=lambda: {},
        ),
    )
    runtime.voice_lab = SimpleNamespace(public_state=lambda: {})
    monkeypatch.setattr(
        mobile_server,
        "build_desktop_dashboard_state",
        lambda *_args, **_kwargs: {
            "core": {"architecture": "13.2", "ok": True},
            "live": {"character": {"name": "Mary"}},
        },
    )

    server, thread = _serve(tmp_path, runtime=runtime)
    try:
        conn = HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        conn.request(
            "GET",
            "/api/experience",
            headers={"Authorization": "Bearer secret"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read())
        rendered = repr(payload)
        assert response.status == 200
        assert payload["metadata"]["character_records"] == 189
        sourcebook_projection = runtime.dashboard_state()["character_sourcebook"]
        assert sourcebook_projection == {
            "version": "13.2",
            "records": 189,
            "sourcebook_hash": "abcdef1234567890abcd",
            "error_count": 1,
        }
        assert "PRIVATE_AUTHORED_SOURCE" not in rendered
        assert "PRIVATE_AUTHORED_EVIDENCE" not in rendered
        assert "PRIVATE_SOURCE_PATH" not in repr(sourcebook_projection)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
