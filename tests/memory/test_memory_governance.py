from __future__ import annotations

from mary.governance.limits import RuntimeLimits
from mary.memory.manager import MemoryManager


def test_episodic_and_semantic_memory_have_hard_capacities():
    limits = RuntimeLimits(episodic_capacity=5, semantic_capacity=4, memory_content_characters=256)
    manager = MemoryManager(limits=limits)

    for index in range(50):
        manager.remember_event(f"event {index}", importance=index / 50)
        manager.remember_fact("test", f"predicate_{index}", f"value {index}", confidence=index / 50)

    assert manager.episodic.count() == 5
    assert manager.semantic.count() == 4
    assert manager.status()["evicted"]["episodic"] > 0
    assert manager.status()["evicted"]["semantic"] > 0


def test_high_importance_old_memory_can_survive_compaction():
    limits = RuntimeLimits(episodic_capacity=3)
    manager = MemoryManager(limits=limits)
    important = manager.remember_event("important anchor", importance=1.0)
    for index in range(20):
        manager.remember_event(f"noise {index}", importance=0.1)

    assert manager.episodic.get(important.id) is not None


def test_recall_and_working_context_are_independently_bounded():
    limits = RuntimeLimits(memory_recall_limit=3, memory_context_working_limit=2, working_memory_capacity=20)
    manager = MemoryManager(limits=limits)
    for index in range(10):
        manager.remember_event(f"blue item {index}")
        manager.remember_working(f"working {index}")

    context = manager.build_context("blue", limit=999)
    assert len(context["relevant_memories"]) <= 3
    assert len(context["working_memory"]) <= 2


def test_memory_content_is_compacted_instead_of_storing_unbounded_raw_text():
    manager = MemoryManager(limits=RuntimeLimits(memory_content_characters=256))
    item = manager.remember_event("A" * 5000)
    assert len(item.content) <= 256
    assert "compacted" in item.content
