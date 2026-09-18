from __future__ import annotations

from pathlib import Path
from threading import RLock
from types import SimpleNamespace

from mary.continuity import WorldModel
from mary.core.service import MaryCoreService
from mary.knowledge import WorldContextItem, WorldContextStore


def test_current_world_context_can_be_found_by_evidence_id():
    store = WorldContextStore()
    item = store.ingest(WorldContextItem(
        topic="Example release",
        summary="A current source reports a release date.",
        source="official source",
        confidence=0.9,
    ))
    assert store.get(item.id) == item
    assert store.get("missing") is None


def test_explicit_world_evidence_acceptance_creates_provenance_bound_belief(tmp_path: Path):
    world = WorldContextStore()
    item = world.ingest(WorldContextItem(
        topic="Example release",
        summary="The official page lists November 19, 2026.",
        source="official publisher",
        lane="games",
        confidence=0.92,
        url="https://example.invalid/release",
    ))

    service = object.__new__(MaryCoreService)
    service._closed = False
    service._turn_lock = RLock()
    service.application = SimpleNamespace(
        ecosystem=SimpleNamespace(world=world),
    )
    service.mary = SimpleNamespace(
        world_model=WorldModel(tmp_path / "world_model.json"),
    )

    result = service.runtime_action({
        "action": "world.accept_evidence",
        "device_id": "creator-test",
        "args": {
            "item_id": item.id,
            "subject": "Example Game",
            "predicate": "release_date",
            "value": "2026-11-19",
            "confidence": 1.0,
        },
    })

    assert result["ok"] is True
    belief = result["belief"]
    assert belief["subject"] == "Example Game"
    assert belief["predicate"] == "release_date"
    assert belief["value"] == "2026-11-19"
    assert belief["authority"] == "verified_external"
    assert belief["confidence"] == 0.92
    assert f"world_context:{item.id}" in belief["evidence_ids"]
    assert service.mary.world_model.status()["current_beliefs"] == 1


def test_world_context_never_promotes_itself():
    store = WorldContextStore()
    item = store.ingest(WorldContextItem(
        topic="Unverified claim",
        summary="This should expire instead of silently becoming durable truth.",
        source="external",
        confidence=0.4,
    ))
    snapshot = store.snapshot()
    assert snapshot["authority"] == "ephemeral_external_context_only"
    assert snapshot["recent"][0]["id"] == item.id
    assert "never mutates character canon" in snapshot["policy"]
