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
