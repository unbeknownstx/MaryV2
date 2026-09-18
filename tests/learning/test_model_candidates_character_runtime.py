import json

from mary.learning import ModelCandidateCatalog


def test_candidate_catalog_loads_reviewed_metadata_without_downloading(tmp_path):
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps({
        "candidates": [{
            "id": "test-lora",
            "kind": "lora_adapter",
            "runtime": "llama.cpp",
            "repository": "example/repo",
            "filename": "adapter.gguf",
            "sha256": "abc123",
            "license": "Apache-2.0",
            "required_base": "example/base",
            "role": ["adapter_lab"],
            "download_url": "https://example.invalid/adapter.gguf",
        }]
    }), encoding="utf-8")
    catalog = ModelCandidateCatalog(path)
    item = catalog.get("test-lora")
    assert item is not None
    assert item.required_base == "example/base"
    assert item.metadata["download_url"].startswith("https://")
    snapshot = catalog.snapshot()
    assert snapshot["count"] == 1
    assert snapshot["policy"].startswith("reviewed optional assets")



def test_candidate_catalog_requires_exact_base_and_runtime_for_direct_adapter_test(tmp_path):
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps({
        "candidates": [
            {
                "id": "qwen-small",
                "kind": "base_model",
                "runtime": "llama.cpp",
                "repository": "example/base-gguf",
                "filename": "base.gguf",
                "upstream_base": "Qwen/Qwen3-0.6B",
            },
            {
                "id": "tiny-lora",
                "kind": "lora_adapter",
                "runtime": "llama.cpp",
                "repository": "example/lora",
                "filename": "adapter.gguf",
                "required_base": "Qwen/Qwen3-0.6B",
            },
            {
                "id": "peft-roleplay",
                "kind": "lora_adapter",
                "runtime": "transformers_peft",
                "repository": "example/peft",
                "filename": "adapter_model.safetensors",
                "required_base": "Qwen/Qwen3-0.6B",
            },
        ]
    }), encoding="utf-8")
    catalog = ModelCandidateCatalog(path)

    direct = catalog.compatibility(
        base_candidate_id="qwen-small",
        adapter_candidate_id="tiny-lora",
    )
    assert direct["exact_base"] is True
    assert direct["runtime_compatible"] is True
    assert direct["directly_testable"] is True

    peft = catalog.compatibility(
        base_candidate_id="qwen-small",
        adapter_candidate_id="peft-roleplay",
    )
    assert peft["exact_base"] is True
    assert peft["runtime_compatible"] is False
    assert peft["directly_testable"] is False

    matrix = catalog.experiment_matrix(
        base_candidate_id="qwen-small",
        adapter_candidate_ids=("tiny-lora", "peft-roleplay"),
    )
    assert matrix["control"]["adapters"] == []
    assert [arm["adapters"] for arm in matrix["adapter_arms"]] == [["tiny-lora"]]
