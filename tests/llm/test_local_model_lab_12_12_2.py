from __future__ import annotations

from mary.mind.local_models import CANDIDATES
from scripts.benchmark_local_models import _character_quality_score, _restraint_score, _speed_score


def test_model_lab_expands_small_candidate_comparison_without_replacing_qwen_baseline():
    by_name = {item.model: item for item in CANDIDATES}
    assert by_name["qwen3:1.7b"].tier == "minimal"
    assert by_name["llama3.2:1b"].approx_size_gb <= 1.3
    assert by_name["gemma3:1b"].tier == "minimal"
    assert "smollm2:1.7b" in by_name
    assert "llama3.2:3b" in by_name
    assert by_name["qwen3:4b"].tier == "baseline"


def test_model_lab_penalizes_assistant_and_theatrical_output():
    natural = "Yeah, that's pretty good. I'd keep it."
    theatrical = "*smirks* Well... destiny has a funny way of finding us!!! Let me know if you'd like more."
    assert _character_quality_score(natural) > _character_quality_score(theatrical)
    assert _restraint_score(natural) > _restraint_score(theatrical)
    assert _speed_score(500) > _speed_score(4000)
