"""
MaryV2 - Memory Integration Tests

Tests Mary's memory architecture as a connected system:

    remember
        ↓
    episodic memory
        ↓
    retrieval
        ↓
    consolidation
        ↓
    semantic memory
"""


from mary.memory.manager import MemoryManager


def test_memory_manager_initializes():
    memory = MemoryManager()

    assert memory.episodic is not None
    assert memory.semantic is not None
    assert memory.working is not None
    assert memory.retrieval is not None
    assert memory.consolidation is not None


def test_remember_creates_episodic_memory():
    memory = MemoryManager()

    result = memory.remember(
        "Mary learned that integration tests are important.",
    )

    assert result is not None
    assert result.content == (
        "Mary learned that integration tests are important."
    )

    assert memory.episodic.count() == 1


def test_recall_finds_episodic_memory():
    memory = MemoryManager()

    memory.remember(
        "Mary learned that integration tests are important.",
    )

    results = memory.recall(
        "integration tests",
    )

    assert isinstance(results, list)
    assert len(results) >= 1

    contents = [
        result.get("content", "")
        for result in results
    ]

    assert any(
        "integration tests" in content
        for content in contents
    )


def test_remember_working_memory():
    memory = MemoryManager()

    result = memory.remember_working(
        "Mary is currently testing her memory system.",
        category="current_task",
        importance=0.8,
    )

    assert result is not None
    assert result["content"] == (
        "Mary is currently testing her memory system."
    )

    assert memory.working.count() == 1


def test_remember_semantic_fact():
    memory = MemoryManager()

    result = memory.remember_fact(
        subject="Mary",
        predicate="is_testing",
        value="memory architecture",
        confidence=0.9,
    )

    assert result is not None
    assert result["subject"] == "Mary"
    assert result["predicate"] == "is_testing"
    assert result["value"] == "memory architecture"
    assert result["confidence"] == 0.9

    assert memory.semantic.count() == 1


def test_memory_status_reports_counts():
    memory = MemoryManager()

    memory.remember(
        "Mary remembers something important.",
    )

    memory.remember_fact(
        subject="Mary",
        predicate="knows",
        value="memory systems",
    )

    memory.remember_working(
        "Current memory test.",
    )

    status = memory.status()

    assert status["episodic"] is True
    assert status["semantic"] is True
    assert status["working"] is True
    assert status["retrieval"] is True
    assert status["consolidation"] is True

    assert status["counts"]["episodic"] == 1
    assert status["counts"]["semantic"] == 1
    assert status["counts"]["working"] == 1


def test_build_context_contains_relevant_memory():
    memory = MemoryManager()

    memory.remember(
        "Mary is learning about artificial intelligence.",
    )

    context = memory.build_context(
        "artificial intelligence",
    )

    assert isinstance(context, dict)
    assert context["query"] == "artificial intelligence"
    assert "relevant_memories" in context
    assert "working_memory" in context

    assert len(context["relevant_memories"]) >= 1