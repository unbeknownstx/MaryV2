from time import monotonic
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.distributed import NodeRegistry
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
    service.register_creator_surface({"surface_id": "creator"})
    return service


def _registration(node_id="device-a"):
    return {
        "node_id": node_id, "display_name": node_id, "host_type": "desktop",
        "platform": "windows", "surface": "desktop",
        "capabilities": [{"name": "personal_search", "private": True}],
    }


def test_durable_proof_reconnects_after_restart_and_rotates_ephemeral_token(tmp_path):
    path = tmp_path / "enrollment.json"
    first = _service(enrollment_state_path=path)
    enrolled = first.register_node(_registration())
    durable, old_token = enrolled["device_credential"], enrolled["node_token"]
    assert durable not in first.enrollment_grant_status()["trusted_devices"][0].values()
    assert durable not in path.read_text(encoding="utf-8")
    assert old_token not in path.read_text(encoding="utf-8")

    second = _service(enrollment_state_path=path)
    reconnected = second.register_node(
        _registration(), device_credential=durable, creator_authorized=False,
    )
    assert reconnected["node_token"] != old_token
    assert "device_credential" not in reconnected
    assert reconnected["session_generation"] == 2
    assert not second.validate_node_token("device-a", old_token)
    with pytest.raises(PermissionError):
        second.register_node(
            _registration(), device_credential="wrong", creator_authorized=False,
        )


def test_durable_proof_cannot_take_over_live_session_or_other_node():
    service = _service()
    enrolled = service.register_node(_registration())
    with pytest.raises(PermissionError, match="current node token"):
        service.register_node(
            _registration(), device_credential=enrolled["device_credential"],
            creator_authorized=False,
        )
    with pytest.raises(PermissionError):
        service.register_node(
            _registration("device-b"), device_credential=enrolled["device_credential"],
            creator_authorized=False,
        )


def test_creator_revoke_forgets_trust_session_grants_and_descriptor(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-secret")
    service = _service(enrollment_state_path=tmp_path / "enrollment.json")
    grant = service.issue_enrollment_grant("device-a")["enrollment_grant"]
    enrolled = service.register_node(_registration())
    task = service.dispatch_capability_task({
        "capability": "personal_search", "intent": "queued", "args": {"query": "queued"},
    })["task"]
    # Ensure there is a claimed/queued task tied to the live descriptor.
    service.mary.node_registry.get("device-a").last_heartbeat_monotonic = monotonic()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/nodes/revoke", headers={"Authorization": "Bearer creator-secret"},
            json={"node_id": "device-a"},
        )
        assert response.status_code == 200
        assert service.mary.node_registry.get("device-a") is None
        assert not service.validate_node_token("device-a", enrolled["node_token"])
        assert service.capability_task_status(task["task_id"])["task"]["status"] == "expired"
        with pytest.raises(PermissionError):
            service.register_node(
                _registration(), device_credential=enrolled["device_credential"],
                creator_authorized=False,
            )
        with pytest.raises(PermissionError):
            service.register_node(
                _registration(), enrollment_grant=grant, creator_authorized=False,
            )
    restarted = _service(enrollment_state_path=tmp_path / "enrollment.json")
    with pytest.raises(PermissionError):
        restarted.register_node(
            _registration(), device_credential=enrolled["device_credential"],
            creator_authorized=False,
        )


def test_deliberate_reenrollment_rotates_durable_proof_and_old_proof_fails(tmp_path):
    path = tmp_path / "enrollment.json"
    first = _service(enrollment_state_path=path)
    original = first.register_node(_registration())
    first.disconnect_node(
        {"node_id": "device-a"},
        node_token=original["node_token"],
    )
    grant = first.issue_enrollment_grant("device-a")["enrollment_grant"]

    replacement = first.register_node(
        _registration(),
        enrollment_grant=grant,
        creator_authorized=False,
    )
    assert replacement["device_credential"] != original["device_credential"]
    assert replacement["session_generation"] == 2

    restarted = _service(enrollment_state_path=path)
    with pytest.raises(PermissionError):
        restarted.register_node(
            _registration(),
            device_credential=original["device_credential"],
            creator_authorized=False,
        )
    recovered = restarted.register_node(
        _registration(),
        device_credential=replacement["device_credential"],
        creator_authorized=False,
    )
    assert recovered["session_generation"] == 3


def test_multiple_trusted_nodes_are_credential_isolated_across_restart(tmp_path):
    path = tmp_path / "enrollment.json"
    first = _service(enrollment_state_path=path)
    node_a = first.register_node(_registration("device-a"))
    node_b = first.register_node(_registration("device-b"))

    restarted = _service(enrollment_state_path=path)
    with pytest.raises(PermissionError):
        restarted.register_node(
            _registration("device-b"),
            device_credential=node_a["device_credential"],
            creator_authorized=False,
        )
    connected_a = restarted.register_node(
        _registration("device-a"),
        device_credential=node_a["device_credential"],
        creator_authorized=False,
    )
    connected_b = restarted.register_node(
        _registration("device-b"),
        device_credential=node_b["device_credential"],
        creator_authorized=False,
    )
    assert connected_a["node"]["node_id"] == "device-a"
    assert connected_b["node"]["node_id"] == "device-b"


def test_corrupt_trust_state_fails_closed_without_projecting_untrusted_fields(tmp_path):
    path = tmp_path / "enrollment.json"
    path.write_text(
        """{
          "version": 2,
          "trusted_devices": [
            {"node_id": "device-a", "credential_digest": "bad", "enrolled_at": "never"}
          ],
          "session_generations": {"device-a": "not-a-number"},
          "audit": [
            {"event": "unknown", "node_id": "device-a", "secret": "DO-NOT-LEAK"}
          ]
        }""",
        encoding="utf-8",
    )
    service = _service(enrollment_state_path=path)

    status = service.enrollment_grant_status()
    assert status["trusted_devices"] == []
    assert "DO-NOT-LEAK" not in repr(status)
    with pytest.raises(PermissionError):
        service.register_node(
            _registration(),
            device_credential="attacker-proof",
            creator_authorized=False,
        )


def test_offline_lifecycle_does_not_weaken_durable_authentication(tmp_path):
    path = tmp_path / "enrollment.json"
    first = _service(enrollment_state_path=path)
    enrolled = first.register_node(_registration())

    restarted = _service(enrollment_state_path=path)
    restarted.set_creator_offline(True)
    restarted.register_node(
        _registration(),
        device_credential=enrolled["device_credential"],
        creator_authorized=False,
    )
    with pytest.raises(RuntimeError, match="sleeping or offline"):
        restarted.dispatch_capability_task({
            "capability": "personal_search",
            "intent": "must stay gated",
            "args": {"query": "private"},
        })

    restarted.set_creator_offline(False)
    with pytest.raises(PermissionError):
        restarted.register_node(
            _registration("device-b"),
            device_credential=enrolled["device_credential"],
            creator_authorized=False,
        )


def test_plaintext_remote_registration_is_rejected_before_grant_consumption(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-secret")
    service = _service()
    grant = service.issue_enrollment_grant("device-a", max_uses=1)
    with TestClient(
        create_app(service),
        base_url="http://remote.example",
        client=("198.51.100.10", 41234),
    ) as client:
        response = client.post(
            "/v1/nodes/register",
            headers={"X-Mary-Enrollment-Grant": grant["enrollment_grant"]},
            json=_registration(),
        )
    assert response.status_code == 426
    status = service.enrollment_grant_status()
    assert status["grants"][0]["remaining_uses"] == 1
    assert status["trusted_devices"] == []


@pytest.mark.parametrize(
    ("client_host", "host_header"),
    [
        ("198.51.100.10", "localhost"),
        ("198.51.100.10", "127.0.0.1"),
        ("127.0.0.1", "core.internal"),
    ],
)
def test_plaintext_registration_cannot_spoof_locality(
    monkeypatch,
    client_host,
    host_header,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-secret")
    service = _service()
    grant = service.issue_enrollment_grant("device-a", max_uses=1)
    with TestClient(
        create_app(service),
        base_url="http://core.internal",
        client=(client_host, 41234),
    ) as client:
        response = client.post(
            "/v1/nodes/register",
            headers={
                "Host": host_header,
                "X-Mary-Enrollment-Grant": grant["enrollment_grant"],
            },
            json=_registration(),
        )
    assert response.status_code == 426
    assert service.enrollment_grant_status()["grants"][0]["remaining_uses"] == 1


def test_enrollment_persistence_failure_rolls_back_without_live_session(
    tmp_path,
    monkeypatch,
):
    service = _service(enrollment_state_path=tmp_path / "enrollment.json")
    grant = service.issue_enrollment_grant(
        "device-a",
        max_uses=1,
    )["enrollment_grant"]
    original_save = service._save_enrollment_state
    monkeypatch.setattr(
        service,
        "_save_enrollment_state",
        lambda: (_ for _ in ()).throw(RuntimeError("disk full")),
    )

    with pytest.raises(RuntimeError, match="disk full"):
        service.register_node(
            _registration(),
            enrollment_grant=grant,
            creator_authorized=False,
        )
    assert service.mary.node_registry.get("device-a") is None
    assert service.enrollment_grant_status()["grants"][0]["remaining_uses"] == 1
    assert service.enrollment_grant_status()["trusted_devices"] == []

    monkeypatch.setattr(service, "_save_enrollment_state", original_save)
    enrolled = service.register_node(
        _registration(),
        enrollment_grant=grant,
        creator_authorized=False,
    )
    assert enrolled["device_credential"]
    assert enrolled["session_generation"] == 1