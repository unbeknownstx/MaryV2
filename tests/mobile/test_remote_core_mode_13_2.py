import json
from collections import deque
from threading import RLock
from types import SimpleNamespace

import pytest

import mary.mobile.server as mobile_server
from mary.protocol.client import MaryProtocolError


class FakeRemoteClient:
    def __init__(
        self,
        base_url,
        *,
        token,
        device_id,
        timeout=120.0,
    ):
        self.base_url = base_url
        self.token = token
        self.device_id = device_id
        self.runtime_actions = []
        self.workspace_actions = []
        self.surface_calls = []

    def surface_register(self, **payload):
        self.surface_calls.append(("register", payload))
        return {"surface_id": "ios-surface"}

    def surface_renew(self, **payload):
        self.surface_calls.append(("renew", payload))
        return {"surface_id": payload["surface_id"], "awake": True}

    def surface_disconnect(self, **payload):
        self.surface_calls.append(("disconnect", payload))
        return {"disconnected": True}

    def surface_wake(self, **payload):
        self.surface_calls.append(("wake", payload))
        return {"awake": True}

    def lifecycle_status(self):
        return {"awake": True, "connected_surfaces": 1}

    def state(self):
        return {
            "core": {
                "architecture": "13.2",
                "service": "mary-core",
                "instance_id": "test-core",
            },
            "mary": {
                "name": "Mary",
            },
            "character": {
                "sourcebook": {
                    "version": "13.2",
                    "records": 189,
                    "sourcebook_hash": "abcdef1234567890abcd",
                    "errors": ["PRIVATE_SOURCE_PATH"],
                    "source_names": ["PRIVATE_AUTHORED_SOURCE"],
                },
            },
            "nodes": {
                "nodes": [],
            },
        }

    def dashboard(self):
        return {
            "relationship": {
                "score": 72,
                "label": "Established",
                "profile_records": 3,
                "history_events": 20,
                "milestones": 1,
            },
            "personality": {
                "traits": [
                    "curious",
                ],
            },
            "curiosities": [
                {
                    "id": "curiosity-1",
                    "question": "What are we building next?",
                }
            ],
            "agency": {
                "goals": 2,
            },
            "retrieval": {
                "mode": "hybrid",
            },
            "perception": {
                "enabled": False,
            },
            "training_feedback": {
                "records": 0,
            },
            "growth": {
                "version": "13.0",
            },
            "engagement": {
                "mode": "dashboard-value",
            },
            "realtime": {
                "phase": "dashboard-value",
            },
            "nodes": {
                "nodes": [
                    {
                        "node_id": "dashboard-node",
                    }
                ],
            },
        }

    def conversation_status(self):
        return {
            "engagement": {
                "mode": "adaptive",
            },
            "realtime": {
                "phase": "idle",
            },
        }

    def growth_status(self):
        return {
            "version": "13.0",
        }

    def nodes(self):
        return {
            "nodes": [],
        }

    def workspace(self):
        return {
            "command": {
                "items": [],
            },
            "arcade": {
                "games": [
                    {
                        "key": "coin",
                        "label": "Coin Flip",
                        "description": "Quick local coin flip.",
                    },
                ],
            },
        }

    def workspace_action(self, action, args=None):
        payload = dict(args or {})
        self.workspace_actions.append((action, payload))
        if action == "arcade.play":
            return {
                "ok": True,
                "game": payload["game"],
                "result": "Heads",
            }
        return {"ok": True}

    def turn(
        self,
        text,
        *,
        conversation_id=None,
        requested_mode=None,
        voice_input=False,
    ):
        return SimpleNamespace(
            response="hello from core",
            request_id="request_mobile_safe",
            turn_id="turn-1",
            effective_mode="adaptive",
            provenance={
                "provider": "groq",
            },
            conversation_state=self.conversation_status(),
            display_hints={
                "delivery_plan": {},
                "dialogue_plan": {},
            },
            state_changes={},
        )

    def runtime_action(self, action, args=None):
        payload = dict(args or {})
        self.runtime_actions.append((action, payload))
        if action == "training.feedback.status":
            return {"records": 0, "persistent": True}
        if action == "training.feedback.record":
            return {
                "ok": True,
                "id": "feedback-1",
                "status": {"records": 1, "persistent": True},
            }
        return {"ok": True, "action": action}


def test_remote_mobile_runtime_does_not_construct_local_mary(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        FakeRemoteClient,
    )

    monkeypatch.setenv(
        "MARY_MOBILE_PROXY_DATA_DIR",
        str(
            tmp_path / "proxy"
        ),
    )

    monkeypatch.setattr(
        mobile_server,
        "create_application",
        lambda *a, **k: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "must not construct Mary"
            )
        ),
    )

    runtime = (
        mobile_server
        .MaryRemoteMobileRuntime(
            "https://core.example",
            token="secret",
            device_id="iphone",
        )
    )

    payload = runtime.chat(
        "hi"
    )

    assert (
        payload["text"]
        == "hello from core"
    )

    assert (
        payload[
            "runtime"
        ][
            "trace"
        ][
            "authority"
        ]
        == "remote_mary_core"
    )
    assert payload["runtime"]["trace"]["request_id"] == "request_mobile_safe"

    assert (
        runtime.status()[
            "mobile"
        ][
            "authority"
        ]
        == "remote_mary_core"
    )
    dashboard = runtime.dashboard_state()
    assert dashboard["character_sourcebook"] == {
        "version": "13.2",
        "records": 189,
        "sourcebook_hash": "abcdef1234567890abcd",
        "error_count": 1,
    }
    assert "PRIVATE_AUTHORED_SOURCE" not in repr(dashboard["character_sourcebook"])
    assert "PRIVATE_SOURCE_PATH" not in repr(dashboard["character_sourcebook"])
    assert dashboard["core_instance_id"] == "test-core"
    assert payload["runtime"]["trace"]["core_instance_id"] == "test-core"


def test_remote_mobile_default_proxy_state_uses_canonical_data_root(
    monkeypatch,
    tmp_path,
):
    canonical_data = tmp_path / "canonical-state"
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        FakeRemoteClient,
    )
    monkeypatch.delenv(
        "MARY_MOBILE_PROXY_DATA_DIR",
        raising=False,
    )
    monkeypatch.setenv(
        "MARY_DATA_DIR",
        str(canonical_data),
    )

    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )

    assert runtime.data_root == canonical_data / "mobile_proxy"
    assert runtime.data_root.is_dir()


def test_remote_mobile_retains_safe_core_request_id_on_turn_failure(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )

    def fail_turn(*_args, **_kwargs):
        raise MaryProtocolError(
            "Mary Core returned HTTP 500.",
            request_id="request_mobile_failure",
            status_code=500,
        )

    runtime.client.turn = fail_turn
    with pytest.raises(MaryProtocolError):
        runtime.chat("private message")

    assert runtime.last_turn_trace() == {
        "request_id": "request_mobile_failure",
        "outcome": "failure",
        "failure_kind": "core_http_failure",
        "error_type": "MaryProtocolError",
        "authority": "remote_mary_core",
        "device_id": "iphone",
        "core_instance_id": "test-core",
    }


def test_remote_mobile_success_trace_drops_private_provenance_and_bad_id(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )
    original_turn = runtime.client.turn

    def adversarial_turn(*args, **kwargs):
        response = original_turn(*args, **kwargs)
        response.request_id = "secret request id with private prose"
        response.provenance = {
            "provider": "groq",
            "model": "safe-model",
            "route": "PRIVATE_ROUTE_CONTEXT",
            "provider_attempts": [{
                "provider": "groq",
                "status": "failure",
                "error": "PRIVATE_PROVIDER_EXCEPTION_OUTPUT",
            }],
            "private": "PRIVATE_MEMORY_EVIDENCE",
        }
        response.display_hints["timings"] = {
            "context_ms": 1.25,
            "private_timing": "PRIVATE_PROMPT",
        }
        return response

    runtime.client.turn = adversarial_turn
    trace = runtime.chat("hi")["runtime"]["trace"]
    serialized = json.dumps(trace, sort_keys=True)
    assert trace["request_id"] == ""
    assert trace["provider_attempts"] == [{
        "provider": "groq",
        "status": "failure",
    }]
    assert trace["timings"]["context_ms"] == 1.25
    assert 0.0 <= trace["elapsed"] <= 86_400.0
    assert "PRIVATE_" not in serialized
    assert runtime.last_turn_trace() == trace


def test_local_finalized_trace_only_retains_allowlisted_content_free_telemetry():
    finalized = mobile_server._finalize_local_mobile_trace(
        {
            "event": "mary.turn.complete",
            "request_id": "request_safe",
            "turn_id": "turn_safe",
            "conversation_id": "conversation_safe",
            "stages": [],
        },
        {
            "turn_id": "PRIVATE_RAW_TURN",
            "provider": "groq",
            "model": "PRIVATE_MODEL_NAME",
            "finish_reason": "PRIVATE_FINISH_REASON",
            "attempts": [
                {
                    "provider": "groq",
                    "status": "success",
                    "elapsed_ms": 12.5,
                    "error": "PRIVATE_PROVIDER_ERROR",
                },
                {
                    "provider": "PRIVATE_PROVIDER",
                    "status": "PRIVATE_STATUS",
                },
            ],
            "timings": {
                "pipeline_ms": 18.0,
                "context_ms": float("nan"),
                "intent_ms": float("inf"),
                "reasoning_ms": float("-inf"),
                "private_timing": "PRIVATE_PROMPT",
            },
            "delivery_plan": {
                "private": "PRIVATE_CREATOR_CONTEXT",
            },
            "local_mind": {
                "private": "PRIVATE_MEMORY",
            },
            "mobile": {
                "lane": "PRIVATE_LANE",
            },
        },
    )

    assert finalized["turn_id"] == "turn_safe"
    assert finalized["model"] == "configured"
    assert finalized["finish_reason"] == "unknown"
    assert finalized["provider_attempts"] == [
        {
            "provider": "groq",
            "status": "success",
            "elapsed_ms": 12.5,
        },
        {
            "provider": "unknown",
            "status": "unknown",
        },
    ]
    assert finalized["timings"] == {"pipeline_ms": 18.0}
    assert "mobile" not in finalized
    assert "PRIVATE_" not in json.dumps(finalized, sort_keys=True)


def test_remote_mobile_trace_query_uses_authenticated_core_client(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )
    calls = []

    def request(method, path):
        calls.append((method, path))
        return {
            "traces": [{
                "request_id": "request-safe",
                "core_instance_id": "test-core",
                "route": "PRIVATE_ROUTE_CONTEXT",
            }],
            "count": 1,
        }

    runtime.client._request = request
    payload = runtime.query_turn_traces(
        request_id="request-safe",
        limit=999,
    )

    assert payload["traces"][0]["core_instance_id"] == "test-core"
    assert "route" not in payload["traces"][0]
    assert "PRIVATE_" not in json.dumps(payload, sort_keys=True)
    assert calls == [(
        "GET",
        "/v1/turn-traces?limit=40&request_id=request-safe",
    )]


def test_local_mobile_trace_query_keeps_bounded_newest_first_history():
    runtime = object.__new__(mobile_server.MaryMobileRuntime)
    runtime._lock = RLock()
    runtime._last_trace = {}
    runtime._recent_turn_traces = deque(maxlen=40)
    for index in range(45):
        runtime._recent_turn_traces.append({
            "request_id": mobile_server.trace_correlation_id(
                f"request-{index}",
                prefix="request",
            ),
            "turn_id": mobile_server.trace_correlation_id(
                f"turn-{index}",
                prefix="turn",
            ),
            "authority": "local_mobile",
        })

    recent = runtime.query_turn_traces(limit=3)
    filtered = runtime.query_turn_traces(turn_id="turn-42", limit=1000)

    assert [item["turn_id"] for item in recent["traces"]] == [
        mobile_server.trace_correlation_id("turn-44", prefix="turn"),
        mobile_server.trace_correlation_id("turn-43", prefix="turn"),
        mobile_server.trace_correlation_id("turn-42", prefix="turn"),
    ]
    assert filtered == {
        "traces": [{
            "request_id": mobile_server.trace_correlation_id(
                "request-42",
                prefix="request",
            ),
            "turn_id": mobile_server.trace_correlation_id(
                "turn-42",
                prefix="turn",
            ),
            "authority": "local_mobile",
        }],
        "count": 1,
        "authority": "local_mobile",
    }
    assert len(runtime._recent_turn_traces) == 40


def test_remote_dashboard_preserves_canonical_core_state(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        FakeRemoteClient,
    )

    monkeypatch.setenv(
        "MARY_MOBILE_PROXY_DATA_DIR",
        str(
            tmp_path / "proxy"
        ),
    )

    runtime = (
        mobile_server
        .MaryRemoteMobileRuntime(
            "https://core.example",
            token="secret",
            device_id="iphone",
        )
    )

    dashboard = (
        runtime
        .dashboard_state()
    )

    assert (
        dashboard[
            "relationship"
        ][
            "label"
        ]
        == "Established"
    )

    assert (
        dashboard[
            "relationship"
        ][
            "profile_records"
        ]
        == 3
    )

    assert (
        dashboard[
            "personality"
        ][
            "traits"
        ]
        == [
            "curious",
        ]
    )

    assert (
        dashboard[
            "curiosities"
        ][0][
            "id"
        ]
        == "curiosity-1"
    )

    assert (
        dashboard[
            "agency"
        ][
            "goals"
        ]
        == 2
    )

    assert (
        dashboard[
            "retrieval"
        ][
            "mode"
        ]
        == "hybrid"
    )

    assert (
        dashboard[
            "perception"
        ][
            "enabled"
        ]
        is False
    )

    assert (
        "training_feedback"
        in dashboard
    )

    # Session-sensitive conversation state should come from the
    # dedicated conversation endpoint rather than stale dashboard data.
    assert (
        dashboard[
            "engagement"
        ][
            "mode"
        ]
        == "adaptive"
    )

    assert (
        dashboard[
            "realtime"
        ][
            "phase"
        ]
        == "idle"
    )

    # Fresh Core state should replace stale dashboard node data.
    assert (
        dashboard[
            "nodes"
        ]
        == {
            "nodes": [],
        }
    )

    assert (
        dashboard[
            "mobile"
        ][
            "authority"
        ]
        == "remote_mary_core"
    )

    assert (
        dashboard[
            "core"
        ][
            "architecture"
        ]
        == "13.2"
    )

    assert (
        dashboard[
            "character"
        ][
            "name"
        ]
        == "Mary"
    )

    assert dashboard["ecosystem"]["arcade"]["games"][0]["key"] == "coin"


def test_remote_arcade_uses_typed_canonical_workspace_action(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )

    result = runtime.bridge_call("playArcade", ["coin", ""])

    assert result == {"ok": True, "game": "coin", "result": "Heads"}
    assert runtime.client.workspace_actions == [
        ("arcade.play", {"game": "coin", "payload": ""}),
    ]


def test_remote_studio_is_explicitly_compatibility_only(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )

    state = runtime.bridge_call("getCreativeWorkspaceState")
    read = runtime.bridge_call("readCreativeTextFile", ["private.txt"])
    write = runtime.bridge_call(
        "saveCreativeTextFile",
        ["private.txt", "do not write"],
    )

    assert state["compatibility_only"] is True
    assert state["files"] == []
    assert "Desktop-only" in state["reason"]
    assert read["ok"] is False
    assert write["ok"] is False
    assert read["compatibility_only"] is True
    assert write["compatibility_only"] is True

def test_remote_mobile_feedback_is_forwarded_to_canonical_core(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example",
        token="secret",
        device_id="iphone",
    )

    runtime.chat("hi")
    result = runtime.bridge_call(
        "recordResponseFeedback",
        ["positive", ["felt_like_mary"], "good"],
    )

    assert result["ok"] is True
    action, payload = runtime.client.runtime_actions[-1]
    assert action == "training.feedback.record"
    assert payload["user_text"] == "hi"
    assert payload["assistant_text"] == "hello from core"
    assert payload["turn_id"] == "turn-1"
    assert payload["rating"] == "positive"

    status = runtime.bridge_call("getTrainingFeedbackState")
    assert status["records"] == 0
    assert runtime.client.runtime_actions[-1][0] == "training.feedback.status"


def test_remote_mobile_surface_lifecycle_uses_bounded_process_surface_id(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    runtime = mobile_server.MaryRemoteMobileRuntime(
        "https://core.example", token="secret", device_id="iphone"
    )

    runtime.surface_register(surface_id="ios surface!" * 30, lease_seconds=999)
    runtime.surface_renew(visible=False, foreground=False, activity="background")
    runtime.surface_wake()
    runtime.surface_disconnect()

    register = runtime.client.surface_calls[0][1]
    assert len(register["surface_id"]) <= 160
    assert register["lease_seconds"] == 300
    assert runtime.client.surface_calls[1][1]["surface_id"] == "ios-surface"
    assert runtime.lifecycle_status()["connected_surfaces"] == 1
