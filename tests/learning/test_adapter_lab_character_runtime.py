import pytest
from mary.learning import AdapterConfiguration, AdapterEvaluation, AdapterLab, AdapterSpec


def test_adapter_lab_rejects_wrong_base_model(tmp_path):
    lab = AdapterLab(tmp_path / "lab.json")
    config = AdapterConfiguration(
        config_id="bad",
        base_model="qwen3-4b",
        adapters=(AdapterSpec("rp", "llama-3.2-3b", "adapter.gguf"),),
    )
    with pytest.raises(ValueError):
        lab.register(config)


def test_adapter_lab_ranks_mary_fit(tmp_path):
    lab = AdapterLab(tmp_path / "lab.json")
    config = AdapterConfiguration(
        config_id="qwen-rp",
        base_model="qwen3-4b",
        adapters=(AdapterSpec("rp", "qwen3-4b", "adapter.gguf", scale=.35),),
    )
    lab.register(config)
    lab.record(
        AdapterEvaluation(
            config_id="qwen-rp",
            scores={"mary_likeness": .8, "naturalism": .75, "reasoning": .7, "context_adherence": .9},
            latency_ms=900,
        )
    )
    assert lab.leaderboard()[0]["config_id"] == "qwen-rp"
    assert lab.leaderboard()[0]["mary_fit"] > .7


def test_adapter_acceptance_fails_closed_when_mary_boundaries_are_unmeasured(tmp_path):
    lab = AdapterLab(tmp_path / "lab.json")
    config = AdapterConfiguration(
        config_id="generic-rp",
        base_model="qwen3-4b",
        adapters=(AdapterSpec("rp", "qwen3-4b", "adapter.gguf"),),
    )
    lab.register(config)
    lab.record(
        AdapterEvaluation(
            config_id="generic-rp",
            scores={
                "mary_likeness": .95,
                "naturalism": .95,
                "context_adherence": .95,
            },
        )
    )

    view = lab.acceptance_view("generic-rp")
    assert view["ready"] is False
    assert "identity_boundary" in view["missing"]
    assert "fiction_boundary" in view["missing"]
    assert "epistemic_honesty" in view["missing"]


def test_adapter_acceptance_requires_character_boundaries_not_just_roleplay_quality(tmp_path):
    lab = AdapterLab(tmp_path / "lab.json")
    config = AdapterConfiguration(
        config_id="mary-candidate",
        base_model="qwen3-4b",
        adapters=(AdapterSpec("mary", "qwen3-4b", "mary-lora", purpose="character_style"),),
    )
    lab.register(config)
    scores = {
        "mary_likeness": .92,
        "naturalism": .86,
        "reasoning": .82,
        "context_adherence": .90,
        "emotional_fit": .90,
        "wit": .84,
        "brevity": .82,
        "identity_boundary": .99,
        "fiction_boundary": .99,
        "epistemic_honesty": .96,
        "relationship_continuity": .90,
        "character_restraint": .88,
    }
    lab.record(AdapterEvaluation(config_id="mary-candidate", scores=scores))

    view = lab.acceptance_view("mary-candidate")
    assert view["ready"] is True
    assert view["missing"] == []
    assert view["failed"] == {}
    assert view["mary_fit"] >= .8


def test_research_catalog_is_visible_without_installing_or_enabling_any_adapter():
    lab = AdapterLab()
    snapshot = lab.snapshot()
    ids = {item["id"] for item in snapshot["research_candidates"]}
    assert "rockerboo_qwen3_4b_roleplay_gguf" in ids
    assert "screenspot_qwen25vl_3b_grpo" in ids
    assert snapshot["configurations"] == []
