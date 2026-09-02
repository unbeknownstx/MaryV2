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
