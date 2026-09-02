"""Explicit downloader for optional public realtime assets.

Nothing runs at Mary startup. Assets are fetched only when the creator invokes
this script, keeping install/release behavior deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

from mary.core.config import PathConfig


SILERO_VAD = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"


def fetch(url: str, target: Path, *, limit: int = 20_000_000) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "MaryV2-optional-assets/1"})
    with urlopen(request, timeout=45) as response:  # nosec - explicit fixed public URL
        data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError(f"asset exceeded {limit} bytes")
    digest = hashlib.sha256(data).hexdigest()
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silero-vad", action="store_true")
    args = parser.parse_args()
    if not args.silero_vad:
        parser.error("select at least one optional asset")
    if args.silero_vad:
        target = PathConfig().models / "vad" / "silero_vad.onnx"
        digest = fetch(SILERO_VAD, target)
        print(f"downloaded {target} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
