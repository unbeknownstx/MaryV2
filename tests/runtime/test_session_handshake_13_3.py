from types import SimpleNamespace
from mary.runtime.session_handshake import build_connected_session_handshake


def test_connected_session_handshake_makes_core_authority_explicit():
    service = SimpleNamespace(
        instance_id="core-abc",
        identity=SimpleNamespace(service="mary-core", mary_architecture="13.3", protocol_version="1"),
    )
    payload = build_connected_session_handshake(service, peer_id="macbook", peer_kind="capability_node", session_generation=4)
    assert payload["instance_id"] == "core-abc"
    assert payload["architecture"] == "13.3"
    assert payload["peer_id"] == "macbook"
    assert payload["session_generation"] == 4
    assert payload["state_authority"] == "core"
    assert payload["continuity"]["peer_owns_identity"] is False
    assert payload["continuity"]["peer_owns_memory"] is False
