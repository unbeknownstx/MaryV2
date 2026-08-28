from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import mary.mobile.server as mobile_server
from mary.core.service import MaryCoreService
from scripts.sync_mobile_web import drift, in_sync
from tests.protocol.test_core_service import FakeApplication

ROOT = Path(__file__).resolve().parents[2]


class _RemoteClient:
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
        self.surface = "client"
        self.last_turn = {}
        self.dispatched = []

    def state(self):
        return {
            "core": {
                "ok": True,
                "architecture": "13.2",
                "instance_id": "core-test",
            },
            "mary": {
                "name": "Mary",
            },
            "nodes": {
                "connected": 1,
                "registered": 1,
                "nodes": [
                    {
                        "node_id": "pc",
                        "connected": True,
                        "capabilities": {
                            "personal_search": {
                                "name": "personal_search",
                                "available": True,
                            }
                        },
                    }
                ],
            },
        }

    def dashboard(self):
        return {
            "relationship": {
                "score": 68,
                "label": "Established",
                "profile_records": 4,
                "history_events": 15,
                "milestones": 1,
            },
            "personality": {
                "traits": [
                    "curious",
                    "warm",
                ],
            },
            "curiosities": [
                {
                    "id": "curiosity-1",
                    "question": "What should we work on next?",
                }
            ],
            "agency": {
                "goals": 1,
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
                "version": "13.2",
            },
            "engagement": {
                "mode": "dashboard-value",
            },
            "realtime": {
                "phase": "dashboard-value",
            },
            "nodes": {
                "connected": 0,
                "registered": 0,
                "nodes": [],
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
            "version": "13.2",
        }

    def nodes(self):
        return self.state()["nodes"]

    def workspace(self):
        return {}

    def turn(
        self,
        text,
        *,
        conversation_id=None,
        requested_mode=None,
        voice_input=False,
    ):
        self.last_turn = {
            "text": text,
            "conversation_id": conversation_id,
            "voice_input": voice_input,
        }

        return SimpleNamespace(
            response="hello from core",
            turn_id="turn-1",
            provenance={
                "provider": "groq",
            },
            conversation_state=self.conversation_status(),
            display_hints={
                "delivery_plan": {
                    "tone": "warm",
                },
                "dialogue_plan": {
                    "drive": "answer",
                    "stance": "responsive",
                    "tone": "warm",
                },
            },
            state_changes={},
        )

    def runtime_action(
        self,
        action,
        args=None,
    ):
        return {
            "ok": True,
            "action": action,
        }

    def workspace_action(
        self,
        action,
        args=None,
    ):
        return {
            "ok": True,
            "action": action,
        }

    def route_capability(
        self,
        capability,
    ):
        return {
            "capability": capability,
            "available": True,
            "selected_node_id": "pc",
        }

    def dispatch_capability_task(
        self,
        capability,
        intent,
        args=None,
    ):
        task_id = "capability_task_test"

        self.dispatched.append(
            (
                capability,
                intent,
                dict(
                    args
                    or {}
                ),
            )
        )

        return {
            "ok": True,
            "task": {
                "task_id": task_id,
                "selected_node_id": "pc",
                "status": "queued",
            },
        }

    def capability_task_status(
        self,
        task_id,
    ):
        return {
            "ok": True,
            "task": {
                "task_id": task_id,
                "selected_node_id": "pc",
                "status": "completed",
                "result": {
                    "count": 1,
                    "items": [
                        {
                            "name": "Unbeknownst Book 1.docx",
                            "relative_path": (
                                "Book 1/Unbeknownst Book 1.docx"
                            ),
                            "kind": "docx",
                            "match": "name",
                            "snippet": "Unbeknownst Book 1",
                        }
                    ],
                    "privacy": (
                        "absolute paths and search roots omitted"
                    ),
                },
            },
        }


def test_mobile_chat_carries_real_conversation_id_and_turnmind(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        _RemoteClient,
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

    payload = runtime.chat(
        "hi",
        conversation_id="project-unbeknownst",
        voice_input=True,
    )

    assert (
        runtime.client.last_turn[
            "conversation_id"
        ]
        == "project-unbeknownst"
    )

    assert (
        runtime.client.last_turn[
            "voice_input"
        ]
        is True
    )

    assert (
        payload[
            "runtime"
        ][
            "conversation_id"
        ]
        == "project-unbeknownst"
    )

    assert (
        payload[
            "runtime"
        ][
            "turn_mind"
        ][
            "tone"
        ]
        == "warm"
    )

    assert (
        runtime.dashboard_state()[
            "mobile"
        ][
            "conversation_id"
        ]
        == "project-unbeknownst"
    )


def test_remote_dashboard_preserves_core_convergence_state(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        _RemoteClient,
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
        == 4
    )

    assert (
        dashboard[
            "personality"
        ][
            "traits"
        ]
        == [
            "curious",
            "warm",
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
        == 1
    )

    assert (
        dashboard[
            "retrieval"
        ][
            "mode"
        ]
        == "hybrid"
    )

    # Conversation-sensitive values should come from the dedicated
    # conversation endpoint rather than a stale dashboard snapshot.
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

    # Current Core state should replace stale dashboard node data.
    assert (
        dashboard[
            "nodes"
        ][
            "connected"
        ]
        == 1
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


def test_remote_mobile_personal_search_uses_typed_device_task(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        _RemoteClient,
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

    result = runtime.bridge_call(
        "personalSearch",
        [
            "Unbeknownst",
            10,
        ],
    )

    assert (
        result[
            "ok"
        ]
        is True
    )

    assert (
        result[
            "selected_node_id"
        ]
        == "pc"
    )

    assert (
        result[
            "results"
        ][0][
            "relative_path"
        ].endswith(
            ".docx"
        )
    )

    assert (
        runtime.client.dispatched[
            0
        ][0]
        == "personal_search"
    )

    assert (
        runtime.client.dispatched[
            0
        ][2]
        == {
            "query": "Unbeknownst",
            "limit": 10,
        }
    )


def test_remote_mobile_can_switch_short_dialogue_session_without_changing_authority(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        mobile_server,
        "MaryClient",
        _RemoteClient,
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

    context = runtime.bridge_call(
        "setConversationId",
        [
            "project-maryv2"
        ],
    )

    assert context == {
        "conversation_id": "project-maryv2",
        "authority": "remote_mary_core",
    }

    assert (
        runtime.bridge_call(
            "getConversationContext"
        )[
            "conversation_id"
        ]
        == "project-maryv2"
    )


def test_core_display_hints_expose_bounded_dialogue_plan_only():
    core = MaryCoreService(
        FakeApplication(),
        instance_id="display-hint-test",
    )

    result = SimpleNamespace(
        metadata={
            "pipeline_values": {},
            "dialogue_plan": {
                "drive": "opine",
                "stance": "opinion",
                "tone": "warm",
                "allow_question": False,
                "initiative": "bounded",
                "previous_expression": {
                    "private": "not exposed",
                },
                "internal_notes": "not exposed",
            },
            "delivery_plan": {
                "tone": "warm",
            },
        }
    )

    hints = core._display_hints(
        result
    )

    assert (
        hints[
            "dialogue_plan"
        ][
            "drive"
        ]
        == "opine"
    )

    assert (
        hints[
            "dialogue_plan"
        ][
            "allow_question"
        ]
        is False
    )

    assert (
        "previous_expression"
        not in hints[
            "dialogue_plan"
        ]
    )

    assert (
        "internal_notes"
        not in hints[
            "dialogue_plan"
        ]
    )


def test_mobile_web_is_a_13_2_first_class_core_client():
    html = (
        ROOT
        / "mobile_web"
        / "index.html"
    ).read_text(
        encoding="utf-8"
    )

    js = (
        ROOT
        / "mobile_web"
        / "app.js"
    ).read_text(
        encoding="utf-8"
    )

    sw = (
        ROOT
        / "mobile_web"
        / "sw.js"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'id="session-sheet"'
        in html
    )

    assert (
        'id="conversation-thread-button"'
        in html
    )

    assert (
        "project-unbeknownst"
        in js
    )

    assert (
        "conversation_id:state.conversationId"
        in js
    )

    assert (
        "TURNMIND → DIALOGUE"
        in js
    )

    assert (
        "DEVICE CAPABILITY NODES"
        in js
    )

    assert (
        "m.reservoir?.records"
        in js
    )

    assert (
        "t.provider_attempts||t.attempts||[]"
        in js
    )

    assert (
        "Search approved files on my devices"
        in js
    )

    assert (
        "maryv2-mobile-shell-v13-2-unified"
        in sw
    )


def test_native_mobile_bundle_is_exact_copy_of_web_source():
    assert in_sync(), drift()