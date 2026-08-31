from time import monotonic
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.distributed import NodeRegistry
from mary.protocol.client import MaryClient
from mary.protocol.server import create_app


class _Mary:
    def __init__(self):
        self.node_registry = NodeRegistry()
        self.engagement = SimpleNamespace(status=lambda: {}, set_mode=lambda mode: {})
        self.realtime = SimpleNamespace(status=lambda: {})
        self.memory = SimpleNamespace(status=lambda: {})
        self.relationship = SimpleNamespace(governance_status=lambda: {})
        self.growth = SimpleNamespace(status=lambda: {})
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {})


class _Application:
    def __init__(self):
        self.mary = _Mary()
        self.state = SimpleNamespace(to_dict=lambda: {})
        self.ecosystem = SimpleNamespace()

    def close(self):
        return True


def _service(**kwargs):
    service = MaryCoreService(_Application(), **kwargs)
    service.register_creator_surface({"surface_id": "test-creator"})
    return service


def _registration(node_id="device-a"):
    return {
        "node_id": node_id,
        "display_name": node_id,
        "host_type": "desktop",
        "platform": "windows",
        "surface": "desktop",
        "capabilities": [{"name": "personal_search", "private": True}],
    }


def test_scoped_grant_enrolls_and_recovers_without_creator_bearer(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-secret")
    service = _service()
    with TestClient(create_app(service)) as client:
        issued = client.post(
            "/v1/nodes/enrollment-grants",
            headers={"Authorization": "Bearer creator-secret"},
            json={"node_id": "device-a", "expires_in_seconds": 300, "max_uses": 2},
        )
        assert issued.status_code == 200
        grant = issued.json()["enrollment_grant"]
        assert issued.json()["grant"]["scope"] == ["node.enroll"]

        enrolled = client.post(
            "/v1/nodes/register",
            headers={"X-Mary-Enrollment-Grant": grant},
            json=_registration(),
        )
        assert enrolled.status_code == 200
        old_token = enrolled.json()["node_token"]
        assert enrolled.json()["session_generation"] == 1

        # The grant is not creator authority.
        for method, path in (
            ("GET", "/v1/state"),
            ("GET", "/v1/workspace"),
            ("POST", "/v1/turn"),
        ):
            response = client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {grant}"},
                json={"text": "private"} if method == "POST" else None,
            )
            assert response.status_code == 401

        node = service.mary.node_registry.get("device-a")
        node.last_heartbeat_monotonic = monotonic() - service.mary.node_registry.stale_after - 1
        recovered = client.post(
            "/v1/nodes/register",
            headers={"X-Mary-Enrollment-Grant": grant},
            json=_registration(),
        )
        assert recovered.status_code == 200
        assert recovered.json()["session_generation"] == 2
        assert recovered.json()["node_token"] != old_token
        assert service.validate_node_token("device-a", old_token) is False

        audit = client.get(
            "/v1/nodes/enrollment-grants",
            headers={"Authorization": "Bearer creator-secret"},
        ).json()["audit"]
        assert [item["event"] for item in audit] == [
            "issued",
            "consumed",
            "trusted",
            "consumed",
            "reenrolled",
        ]
        assert grant not in repr(audit)


def test_grant_is_node_bound_use_limited_and_cannot_take_over_live_id():
    service = _service()
    grant = service.issue_enrollment_grant("device-a", max_uses=2)["enrollment_grant"]

    with pytest.raises(PermissionError, match="scoped enrollment"):
        service.register_node(
            _registration("device-b"),
            enrollment_grant=grant,
            creator_authorized=False,
        )

    enrolled = service.register_node(
        _registration(), enrollment_grant=grant, creator_authorized=False,
    )
    with pytest.raises(PermissionError, match="current node token"):
        service.register_node(
            _registration(), enrollment_grant=grant, creator_authorized=False,
        )
    service.disconnect_node({"node_id": "device-a"}, node_token=enrolled["node_token"])
    recovered = service.register_node(
        _registration(), enrollment_grant=grant, creator_authorized=False,
    )
    service.disconnect_node({"node_id": "device-a"}, node_token=recovered["node_token"])
    with pytest.raises(PermissionError, match="scoped enrollment"):
        service.register_node(
            _registration(), enrollment_grant=grant, creator_authorized=False,
        )


def test_grant_digest_and_audit_survive_core_restart_without_raw_grant(tmp_path):
    path = tmp_path / "node-enrollment.json"
    first = _service(enrollment_state_path=path)
    grant = first.issue_enrollment_grant("device-a", max_uses=2)["enrollment_grant"]
    first.register_node(
        _registration(), enrollment_grant=grant, creator_authorized=False,
    )

    persisted = path.read_text(encoding="utf-8")
    assert grant not in persisted
    second = _service(enrollment_state_path=path)
    recovered = second.register_node(
        _registration(), enrollment_grant=grant, creator_authorized=False,
    )
    assert recovered["session_generation"] == 2
    assert [item["event"] for item in second.enrollment_grant_status()["audit"]] == [
        "issued",
        "consumed",
            "trusted",
        "consumed",
            "reenrolled",
    ]


def test_junk_node_token_cannot_bootstrap_unknown_node(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-secret")
    service = _service()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/nodes/register",
            headers={"X-Mary-Node-Token": "attacker-chosen"},
            json=_registration("attacker-node"),
        )
    assert response.status_code == 401
    assert service.mary.node_registry.get("attacker-node") is None


def test_client_sends_grant_alongside_stale_node_token(monkeypatch):
    observed = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"ok": true, "node_token": "replacement"}'

    def fake_urlopen(request, timeout):
        del timeout
        observed.update(dict(request.header_items()))
        return _Response()

    monkeypatch.setattr("mary.protocol.client.urlopen", fake_urlopen)
    client = MaryClient(
        "https://core.invalid",
        enrollment_grant="bounded-grant",
        device_id="device-a",
    )
    client._node_token = "stale-session-token"
    client.register_node(
        display_name="device-a",
        host_type="desktop",
        platform="windows",
        surface="desktop",
        capabilities=[],
    )
    assert observed["X-mary-node-token"] == "stale-session-token"
    assert observed["X-mary-enrollment-grant"] == "bounded-grant"
    assert "Authorization" not in observed


def test_stale_heartbeat_requires_grant_recovery_and_expires_prior_work():
    service = _service()
    grant = service.issue_enrollment_grant("device-a", max_uses=2)["enrollment_grant"]
    enrolled = service.register_node(
        _registration(), enrollment_grant=grant, creator_authorized=False,
    )
    old_token = enrolled["node_token"]
    claimed = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Claimed in old session",
        "args": {"query": "claimed"},
    })["task"]
    queued = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Queued in old session",
        "args": {"query": "queued"},
    })["task"]
    service.poll_capability_task({"node_id": "device-a"}, node_token=old_token)

    node = service.mary.node_registry.get("device-a")
    node.last_heartbeat_monotonic = monotonic() - service.mary.node_registry.stale_after - 1
    with pytest.raises(RuntimeError, match="re-enrollment"):
        service.heartbeat_node({"node_id": "device-a"}, node_token=old_token)

    recovered = service.register_node(
        _registration(),
        node_token=old_token,
        enrollment_grant=grant,
        creator_authorized=False,
    )
    assert recovered["node_token"] != old_token
    assert recovered["session_generation"] == 2
    for task_id in (claimed["task_id"], queued["task_id"]):
        assert service.capability_task_status(task_id)["task"]["status"] == "expired"