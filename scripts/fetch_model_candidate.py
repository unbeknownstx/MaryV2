"""Explicit optional model/LoRA candidate downloader.

This script never runs at Mary startup.  It exists so a creator can fetch one
research-verified candidate, verify its SHA256, and keep large weights outside
canonical Mary state.  The manifest is intentionally small and reviewable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from mary.core.config import PathConfig

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "models" / "candidates" / "model_candidates.json"
DEFAULT_TARGET = PathConfig().models


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def candidate_by_id(candidate_id: str) -> dict:
    for item in load_manifest().get("candidates", []):
        if item.get("id") == candidate_id:
            return dict(item)
    raise KeyError(f"unknown candidate: {candidate_id}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolved_target_dir(item: dict, requested: Path | None = None) -> Path:
    if requested is not None:
        return Path(requested).expanduser()
    group = str(item.get("asset_group") or ("llm" if item.get("kind") in {"base_model", "fine_tuned_model", "lora_adapter"} else "misc")).strip().lower()
    safe = group if group in {"llm", "stt", "vad", "vision", "motion", "tts", "misc"} else "misc"
    return PathConfig().models / safe


def download(item: dict, target_dir: Path | None = None) -> Path:
    target_dir = resolved_target_dir(item, target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / item["filename"]
    temporary = target.with_name(f".{target.name}.part")
    request = Request(item["download_url"], headers={"User-Agent": "MaryV2-model-lab/1"})
    with urlopen(request, timeout=60) as response, temporary.open("wb") as output:  # nosec B310 - fixed manifest reviewed in source
        while True:
            chunk = response.read(4 * 1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    expected = str(item.get("sha256") or "").strip().lower()
    actual = sha256_file(temporary)
    if expected and actual != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"SHA256 mismatch for {item['id']}: expected {expected}, got {actual}")
    temporary.replace(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", nargs="?", help="candidate id")
    parser.add_argument("--list", action="store_true", help="list reviewed candidates")
    parser.add_argument("--download", action="store_true", help="perform explicit network download")
    parser.add_argument("--target-dir", type=Path, default=None, help="override Mary model asset group directory")
    parser.add_argument("--verify", type=Path, help="verify an already-downloaded file against selected candidate")
    args = parser.parse_args()

    manifest = load_manifest()
    if args.list:
        for item in manifest.get("candidates", []):
            print(f"{item['id']}: {item['kind']} {item['approx_size']} {item['license']}")
        return 0
    if not args.candidate:
        parser.error("candidate is required unless --list is used")
    item = candidate_by_id(args.candidate)
    print(json.dumps(item, indent=2))
    if args.verify:
        actual = sha256_file(args.verify)
        expected = str(item.get("sha256") or "").lower()
        print(f"sha256={actual}")
        if expected and actual != expected:
            raise SystemExit("verification failed")
        print("verification passed")
    if args.download:
        target = download(item, args.target_dir)
        print(f"downloaded {target}")
        print(f"sha256={sha256_file(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
