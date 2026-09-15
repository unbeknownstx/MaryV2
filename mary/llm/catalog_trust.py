"""Signed catalog provenance and freshness policy for MaryV2 13.64.

Catalogs are advisory routing metadata.  They can never grant permissions,
change Mary identity/state, or silently replace creator configuration.
Signature verification is injected so the core does not acquire a mandatory
crypto/network dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Callable

VERSION = "13.64"


@dataclass(frozen=True)
class CatalogEnvelope:
    payload: bytes
    signature: bytes
    key_id: str
    issued_at: datetime
    expires_at: datetime
    sequence: int

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class CatalogDecision:
    accepted: bool
    reason: str
    digest: str
    sequence: int
    key_id: str
    authority: str = "routing_metadata_only"


class CatalogTrustPolicy:
    def __init__(self, pinned_key_ids: set[str], *, max_future_skew_seconds: int = 300) -> None:
        self.pinned_key_ids = frozenset(str(k).strip() for k in pinned_key_ids if str(k).strip())
        self.max_future_skew_seconds = max(0, min(3600, int(max_future_skew_seconds)))
        self.last_sequence = -1

    def verify(self, envelope: CatalogEnvelope, verifier: Callable[[str, bytes, bytes], bool], *, now: datetime | None = None) -> CatalogDecision:
        now = now or datetime.now(timezone.utc)
        if envelope.issued_at.tzinfo is None or envelope.expires_at.tzinfo is None:
            return CatalogDecision(False, "timezone_required", envelope.digest, envelope.sequence, envelope.key_id)
        if envelope.key_id not in self.pinned_key_ids:
            return CatalogDecision(False, "untrusted_key", envelope.digest, envelope.sequence, envelope.key_id)
        if envelope.sequence <= self.last_sequence:
            return CatalogDecision(False, "rollback_or_replay", envelope.digest, envelope.sequence, envelope.key_id)
        if envelope.issued_at.timestamp() > now.timestamp() + self.max_future_skew_seconds:
            return CatalogDecision(False, "issued_in_future", envelope.digest, envelope.sequence, envelope.key_id)
        if now >= envelope.expires_at:
            return CatalogDecision(False, "expired", envelope.digest, envelope.sequence, envelope.key_id)
        if not verifier(envelope.key_id, envelope.payload, envelope.signature):
            return CatalogDecision(False, "bad_signature", envelope.digest, envelope.sequence, envelope.key_id)
        self.last_sequence = envelope.sequence
        return CatalogDecision(True, "verified", envelope.digest, envelope.sequence, envelope.key_id)
