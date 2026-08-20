from __future__ import annotations

from mary.governance.limits import RuntimeLimits
from mary.memory.manager import MemoryManager
from mary.relationship.manager import RelationshipManager


def test_memory_recovers_from_finite_backup_after_primary_corruption(tmp_path):
    path = tmp_path / "memory.json"
    limits = RuntimeLimits(backup_generations=2, episodic_capacity=20)
    manager = MemoryManager(storage_path=path, auto_save=False, limits=limits)
    manager.remember_event("first durable event")
    assert manager.save()
    manager.remember_event("second durable event")
    assert manager.save()

    path.write_text("{broken", encoding="utf-8")
    recovered = MemoryManager(storage_path=path, auto_save=False, limits=limits)
    assert recovered.load() is True
    assert recovered.recovered_from_backup is True
    assert recovered.episodic.count() >= 1


def test_backup_chain_never_exceeds_configured_generations(tmp_path):
    path = tmp_path / "memory.json"
    limits = RuntimeLimits(backup_generations=2)
    manager = MemoryManager(storage_path=path, limits=limits)
    for index in range(8):
        manager.remember_event(str(index))
        assert manager.save()

    backups = list(tmp_path.glob("memory.json.bak*"))
    assert len(backups) <= 2


def test_relationship_state_compacts_and_recovers(tmp_path):
    path = tmp_path / "relationship.json"
    limits = RuntimeLimits(relationship_event_capacity=5, backup_generations=2)
    manager = RelationshipManager(path=path, limits=limits)
    for index in range(20):
        manager.history.record("interaction", f"event {index}", importance=0.1)
    manager.history.record("milestone", "important", importance=1.0)
    manager.save()
    manager.save()  # create backup
    assert len(manager.history.events) <= 5
    assert any(item.get("description") == "important" for item in manager.history.events)

    path.write_text("bad json", encoding="utf-8")
    restarted = RelationshipManager(path=path, limits=limits)
    restarted.load()
    assert restarted.recovered_from_backup is True
    assert len(restarted.history.events) <= 5
