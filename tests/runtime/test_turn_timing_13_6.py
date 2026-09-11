import pytest

from mary.runtime.turn_timing import TurnLatencyProfiler


def test_turn_profiler_records_only_allowed_named_stages():
    profiler = TurnLatencyProfiler("turn-1")
    profiler.record_ms("provider", 42.5)
    profiler.record_ms("tts", 11.0)
    result = profiler.breakdown()
    assert result["stages_ms"]["provider"] == 42.5
    assert result["stages_ms"]["tts"] == 11.0
    assert set(result) == {"turn_id", "stages_ms", "total_ms", "unaccounted_ms", "semantics"}
    assert set(result["stages_ms"]).issubset(TurnLatencyProfiler.ALLOWED_STAGES)
    assert all(isinstance(value, float) for value in result["stages_ms"].values())


def test_stage_context_accumulates_and_total_is_nonnegative():
    profiler = TurnLatencyProfiler("turn-2")
    with profiler.stage("cognition"):
        sum(range(100))
    with profiler.stage("cognition"):
        sum(range(100))
    result = profiler.breakdown()
    assert result["stages_ms"]["cognition"] >= 0.0
    assert result["total_ms"] >= 0.0


def test_unknown_stage_is_rejected():
    profiler = TurnLatencyProfiler("turn-3")
    with pytest.raises(ValueError):
        profiler.record_ms("arbitrary-secret-stage", 1)
