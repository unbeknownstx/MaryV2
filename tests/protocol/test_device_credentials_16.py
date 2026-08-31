from __future__ import annotations

import os
import stat

import pytest

from mary.protocol.client import MaryClient
from mary.protocol.credential_store import NodeCredentialStore
from mary.runtime.gateway import RemoteMaryGateway, gateway_from_environment


class _Store:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.saved: list[tuple[str, str]] = []

    def load(self, node_id: str) -> str:
        assert node_id == "node-a"
        return self.value

    def save(self, node_id: str, credential: str) -> None:
        self.saved.append((node_id, credential))
        self.value = credential


def test_registration_uses_and_persists_durable_credential_without_leaking_response(monkeypatch):
    observed: list[dict[str, str]] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"node_token":"session-only","device_credential":"durable-value"}'

    def fake_urlopen(request, timeout):
        del timeout
        observed.append(dict(request.header_items()))
        return Response()

    monkeypatch.setattr("mary.protocol.client.urlopen", fake_urlopen)
    store = _Store("previous-durable-value")
    client = MaryClient("https://core.invalid", device_id="node-a", credential_store=store)
    response = client.register_node(
        display_name="node-a", host_type="node", platform="windows",
        surface="windows_node", capabilities=[],
    )

    assert observed[0]["X-mary-device-credential"] == "previous-durable-value"
    assert store.saved == [("node-a", "durable-value")]
    assert "device_credential" not in response
    assert client._node_token == "session-only"

    client.health()
    assert "X-mary-device-credential" not in observed[1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions are platform-specific")
def test_posix_credential_store_recovers_only_from_private_file(tmp_path):
    store = NodeCredentialStore(tmp_path / "credentials")
    store.save("node/a", "durable-value")
    credential_file = next(store.root.glob("*.credential"))
    assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600
    assert "node/a" not in credential_file.name
    assert store.load("node/a") == "durable-value"

    credential_file.chmod(0o644)
    with pytest.raises(RuntimeError, match="unsafe permissions"):
        store.load("node/a")


def test_node_gateway_accepts_stored_credential_without_migration_grant(monkeypatch):
    class StoredCredential:
        def load(self, node_id):
            assert node_id == "node-a"
            return "stored-value"

        def save(self, node_id, credential):
            raise AssertionError("not used while creating the gateway")

    monkeypatch.setenv("MARY_CORE_URL", "https://core.example")
    monkeypatch.delenv("MARY_CORE_TOKEN", raising=False)
    monkeypatch.delenv("MARY_NODE_ENROLLMENT_GRANT", raising=False)
    monkeypatch.delenv("MARY_NODE_DEVICE_CREDENTIAL", raising=False)
    monkeypatch.setattr("mary.runtime.gateway.NodeCredentialStore", StoredCredential)

    gateway = gateway_from_environment(
        device_id="node-a", surface="windows_node", node_only=True,
    )

    assert isinstance(gateway, RemoteMaryGateway)
    assert gateway.client.enrollment_grant == ""
    assert gateway.client._device_credential == "stored-value"


def test_durable_credential_refuses_non_loopback_plaintext_transport():
    client = MaryClient(
        "http://core.example",
        device_id="node-a",
        credential_store=_Store("durable-value"),
    )
    with pytest.raises(RuntimeError, match="require HTTPS"):
        client.register_node(
            display_name="node-a",
            host_type="node",
            platform="windows",
            surface="windows_node",
            capabilities=[],
        )


def test_initial_enrollment_refuses_non_loopback_plaintext_transport():
    client = MaryClient(
        "http://core.example",
        device_id="node-a",
        enrollment_grant="one-time-grant",
        credential_store=_Store(),
    )
    with pytest.raises(RuntimeError, match="require HTTPS"):
        client.register_node(
            display_name="node-a",
            host_type="node",
            platform="windows",
            surface="windows_node",
            capabilities=[],
        )


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions are platform-specific")
def test_posix_credential_store_rejects_symlinked_root(tmp_path):
    real_root = tmp_path / "real"
    real_root.mkdir(mode=0o700)
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)
    store = NodeCredentialStore(linked_root)

    with pytest.raises(RuntimeError, match="unsafe permissions"):
        store.save("node-a", "durable-value")