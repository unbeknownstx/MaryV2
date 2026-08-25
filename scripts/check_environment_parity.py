"""Export or compare a display-safe MaryV2 runtime configuration profile.

The profile intentionally contains no API keys, tokens, private memories, or
creator data.  It is designed to make Windows/macOS/Replit configuration drift
obvious without requiring the user to reveal secrets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from mary.core.config import Config
from mary.runtime.release import APP_VERSION


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def snapshot() -> dict[str, Any]:
    config = Config.from_environment()
    llm = config.llm
    return {
        "schema": 1,
        "mary_version": APP_VERSION,
        "routing": {
            "strategy": getattr(llm, "routing_strategy", ""),
            "provider": getattr(llm, "provider", ""),
            "task_order": list(getattr(llm, "free_provider_order", []) or []),
            "conversation_order": list(getattr(llm, "conversation_provider_order", []) or []),
            "fallbacks": list(getattr(llm, "fallback_providers", []) or []),
        },
        "models": {
            "default": getattr(llm, "model", ""),
            "groq": _env("MARY_GROQ_MODEL"),
            "gemini": _env("MARY_GEMINI_MODEL"),
            "openrouter": _env("MARY_OPENROUTER_MODEL"),
            "ollama": _env("MARY_OLLAMA_MODEL"),
            "openai": _env("MARY_OPENAI_MODEL"),
        },
        "conversation": {
            "mode": _env("MARY_CONVERSATION_MODE", "adaptive"),
        },
        "voice": {
            "tts_provider": _env("MARY_TTS_PROVIDER", "off"),
            "elevenlabs_model": _env("MARY_ELEVENLABS_MODEL", "eleven_flash_v2_5"),
            "dynamic_delivery": _env("MARY_TTS_DYNAMIC_DELIVERY", "false"),
            "stt_provider": _env("MARY_STT_PROVIDER", "groq"),
            "stt_model": _env("MARY_STT_MODEL", "whisper-large-v3-turbo"),
        },
    }


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten(value[key], child))
        return out
    return {prefix: value}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", metavar="PATH")
    parser.add_argument("--compare", metavar="PATH")
    args = parser.parse_args()
    current = snapshot()

    if args.export:
        path = Path(args.export)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote display-safe Mary configuration profile: {path}")

    if args.compare:
        other = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        a, b = _flatten(other), _flatten(current)
        keys = sorted(set(a) | set(b))
        differences = [(k, a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)]
        print("MARYV2 ENVIRONMENT PARITY")
        print("=" * 72)
        if not differences:
            print("MATCH: portable configuration is identical.")
            return 0
        for key, expected, actual in differences:
            print(f"DIFF {key}: profile={expected!r} current={actual!r}")
        print(f"Differences: {len(differences)}")
        return 2

    if not args.export and not args.compare:
        print(json.dumps(current, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
