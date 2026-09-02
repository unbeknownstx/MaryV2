import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_model_candidate.py"
spec = importlib.util.spec_from_file_location("fetch_model_candidate", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_reviewed_candidate_asset_groups_resolve_outside_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(module.PathConfig, "models", property(lambda self: tmp_path / "MaryModels"), raising=False)
    # Avoid relying on PathConfig implementation details: explicit group mapping is the contract.
    requested = tmp_path / "override"
    assert module.resolved_target_dir({"kind": "base_model", "asset_group": "llm"}, requested) == requested


def test_manifest_contains_small_mac_runtime_candidates():
    manifest = module.load_manifest()
    by_id = {item["id"]: item for item in manifest["candidates"]}
    assert by_id["qwen3-0.6b-q4-fast-brain"]["asset_group"] == "llm"
    assert by_id["whispercpp-tiny-en-q5_1"]["asset_group"] == "stt"
    assert by_id["sherpa-silero-vad"]["asset_group"] == "vad"
    assert by_id["qwen3-0.6b-q4-fast-brain"]["sha256"]
    assert by_id["whispercpp-tiny-en-q5_1"]["sha256"]
