import json

from mary.memory.manager import MemoryManager


def test_stale_manager_does_not_overwrite_externally_replaced_memory(tmp_path):
    path = tmp_path / "memory.json"

    original = {
        "version": 2,
        "policy": "bounded_selective_persistence",
        "episodic": [],
        "semantic": [],
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    manager = MemoryManager()
    assert manager.configure_persistence(path, auto_save=True, load=True)

    external = {
        "version": 2,
        "policy": "bounded_selective_persistence",
        "episodic": [
            {
                "id": "episode_external",
                "content": "new canonical state",
                "timestamp": "2026-08-26T00:00:00+00:00",
                "importance": 0.8,
                "source": "migration",
                "event_type": "migration",
                "participants": [],
                "emotional_context": {},
                "metadata": {},
            }
        ],
        "semantic": [],
    }

    external_text = json.dumps(external, indent=2)
    path.write_text(external_text, encoding="utf-8")

    assert manager.save() is False
    assert path.read_text(encoding="utf-8") == external_text
