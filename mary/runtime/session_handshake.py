"""Display-safe connected-session contract for MaryV2 13.3.

Inspired by mature realtime character/game bridges, every reconnect receives
explicit metadata describing *which Mary Core* accepted the session and what
protocol/architecture contract is active.  This prevents surfaces/nodes from
silently assuming they are talking to the expected runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ConnectedSessionHandshake:
    instance_id: str
    service: str
    architecture: str
    protocol_version: str
    peer_id: str
    peer_kind: str
    session_generation: int = 0
    canonical_identity: str = "mary"
    state_authority: str = "core"
    accepted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload["accepted_at"]:
            payload["accepted_at"] = datetime.now(timezone.utc).isoformat()
        payload["session_generation"] = max(0, int(self.session_generation))
        payload["continuity"] = {
            "same_character_contract": True,
            "peer_owns_identity": False,
            "peer_owns_memory": False,
            "peer_owns_relationship": False,
        }
        return payload


def build_connected_session_handshake(
    service: Any,
    *,
    peer_id: str,
    peer_kind: str,
    session_generation: int = 0,
) -> dict[str, Any]:
    identity = getattr(service, "identity", None)
    return ConnectedSessionHandshake(
        instance_id=str(getattr(service, "instance_id", ""))[:160],
        service=str(getattr(identity, "service", "mary-core"))[:64],
        architecture=str(getattr(identity, "mary_architecture", "unknown"))[:32],
        protocol_version=str(getattr(identity, "protocol_version", "unknown"))[:32],
        peer_id=str(peer_id or "unknown")[:160],
        peer_kind=str(peer_kind or "client")[:64],
        session_generation=session_generation,
    ).to_dict()
