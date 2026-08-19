from mary.runtime.application import create_persistent_mary


def test_create_persistent_mary_configures_and_reloads_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"

    first = create_persistent_mary(memory_path=memory_path)
    first.remember(
        "persistent factory test memory",
        memory_type="episodic",
        importance=0.9,
        metadata={"source": "test"},
    )

    assert memory_path.exists()
    assert first.memory.auto_save is True
    assert first.memory.storage_path == memory_path

    second = create_persistent_mary(memory_path=memory_path)
    recalled = second.memory.recall("persistent factory test memory")

    assert any(
        "persistent factory test memory" in str(item.get("content", ""))
        for item in recalled
    )
