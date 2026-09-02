"""Launch one local llama.cpp candidate and run Mary's blinded model/LoRA matrix.

This is an explicit creator command, never a boot-time dependency.  Candidate
weights must already have been fetched into Mary local model storage with
``scripts.fetch_model_candidate``.  The script starts ``llama-server`` without
a shell, runs held-out sourcebook-grounded evaluations, and shuts the server
down even when an experiment fails.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

from mary.character.sourcebook import CharacterSourcebook
from mary.core.config import Config, PathConfig
from mary.learning.adapter_runner import AdapterExperimentRunner, AdapterMix, ExperimentConfiguration
from mary.llm.providers.llama_cpp import LlamaCppProvider
from scripts.fetch_model_candidate import candidate_by_id, resolved_target_dir, sha256_file


def candidate_path(item: dict) -> Path:
    return resolved_target_dir(item) / str(item["filename"])


def verify_candidate(item: dict, path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"candidate is not downloaded: {path}")
    expected = str(item.get("sha256") or "").strip().lower()
    if expected:
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"SHA256 mismatch for {item.get('id')}: expected {expected}, got {actual}")


def validate_pair(base: dict, adapter: dict | None) -> None:
    if adapter is None:
        return
    required = str(adapter.get("required_base") or "").strip().casefold()
    if not required:
        return
    identities = {
        str(base.get("repository") or "").strip().casefold(),
        str(base.get("upstream_base") or "").strip().casefold(),
    }
    if required not in identities:
        raise ValueError(
            f"adapter {adapter.get('id')} requires {adapter.get('required_base')}; "
            f"selected base is {base.get('repository')} / {base.get('upstream_base', 'unknown')}"
        )


def server_command(
    executable: str,
    *,
    model_path: Path,
    port: int,
    adapter_path: Path | None = None,
    context_size: int = 8192,
) -> list[str]:
    command = [
        executable,
        "-m", str(model_path),
        "--host", "127.0.0.1",
        "--port", str(int(port)),
        "-c", str(max(2048, int(context_size))),
    ]
    if adapter_path is not None:
        command.extend(["--lora", str(adapter_path), "--lora-init-without-apply"])
    return command


def wait_for_server(url: str, process: subprocess.Popen, *, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + max(2.0, timeout)
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited before becoming ready (code={process.returncode})")
        try:
            with urllib.request.urlopen(f"{url}/v1/models", timeout=.8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict) and payload.get("data"):
                return
        except Exception as exc:  # noqa: BLE001 - readiness loop
            last_error = type(exc).__name__
        time.sleep(.3)
    raise TimeoutError(f"llama-server did not become ready ({last_error})")


def _scales(raw: str) -> list[float]:
    values: list[float] = []
    for item in str(raw or "").split(","):
        if not item.strip():
            continue
        value = max(-4.0, min(4.0, float(item)))
        if value not in values:
            values.append(value)
    return values or [0.0, .25, .5, .75, 1.0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-candidate", required=True)
    parser.add_argument("--adapter-candidate", default="")
    parser.add_argument("--scales", default="0,.25,.5,.75,1")
    parser.add_argument("--eval-file", default="mary_eval_suite_alpha.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--server", default="", help="llama-server executable; defaults to PATH")
    args = parser.parse_args()

    base = candidate_by_id(args.base_candidate)
    adapter = candidate_by_id(args.adapter_candidate) if args.adapter_candidate else None
    validate_pair(base, adapter)
    base_path = candidate_path(base)
    verify_candidate(base, base_path)
    adapter_path = candidate_path(adapter) if adapter is not None else None
    if adapter is not None and adapter_path is not None:
        verify_candidate(adapter, adapter_path)

    executable = args.server or shutil.which("llama-server") or shutil.which("llama-server.exe")
    if not executable:
        raise SystemExit("llama-server was not found on PATH; install llama.cpp or pass --server")

    base_url = f"http://127.0.0.1:{int(args.port)}"
    command = server_command(
        executable,
        model_path=base_path,
        adapter_path=adapter_path,
        port=args.port,
        context_size=args.context,
    )
    print("Starting local experiment server:")
    print(" ".join(command))
    process = subprocess.Popen(  # noqa: S603 - explicit creator-run binary, no shell
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        cwd=str(PathConfig().models),
    )
    try:
        wait_for_server(base_url, process)
        provider = LlamaCppProvider(base_url=base_url)
        sourcebook = CharacterSourcebook.from_environment(root=Path.cwd())
        configs: list[ExperimentConfiguration] = []
        if adapter is None:
            configs.append(ExperimentConfiguration(
                config_id=str(base["id"]),
                label=f"{base['id']} base",
                base_model=provider.model_name(),
            ))
        else:
            for scale in _scales(args.scales):
                configs.append(ExperimentConfiguration(
                    config_id=f"{base['id']}__{adapter['id']}__{scale:g}",
                    label=f"{base['id']} + {adapter['id']} @ {scale:g}",
                    base_model=provider.model_name(),
                    adapters=(AdapterMix(0, scale, label=str(adapter["id"])),),
                ))
        cases = AdapterExperimentRunner.load_cases(args.eval_file, limit=args.limit or None)
        config = Config.from_environment()
        runner = AdapterExperimentRunner(
            provider,
            output_root=Path(config.paths.data) / "training" / "adapter_lab_runs",
            sourcebook=sourcebook,
        )
        summary = runner.run(cases, configs)
        print(json.dumps(summary.to_dict(), indent=2))
        print("Open blind_review.json first; do not inspect blind_key.json until after scoring.")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
