"""Safe MaryV2 13.x system doctor.

No provider generation occurs unless --live-providers is supplied. Secrets are
reported only as present/absent and are never printed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from mary.runtime.application import create_application
from mary.runtime.release import APP_VERSION


def yn(value: object) -> str:
    return "YES" if bool(value) else "NO"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-providers", action="store_true")
    args = parser.parse_args()
    app = create_application(name="mary_13_doctor")
    mary = app.mary
    env = mary.runtime_environment.snapshot()
    growth = mary.growth.status()
    engagement = mary.engagement.status()
    realtime = mary.realtime.status()
    nodes = mary.node_registry.snapshot()
    retrieval = mary.mind.retrieval.status()
    memory = mary.memory.status()
    print(f"MARYV2 {APP_VERSION} SYSTEM DOCTOR")
    print("=" * 72)
    print(f"Release: {APP_VERSION}")
    print(f"Host: {env.get('host_type')} / {env.get('platform')}")
    print(f"Conversation route: {' -> '.join(env.get('effective_conversation_route', []) or []) or 'none available on this host'}")
    print(f"Task route: {' -> '.join(env.get('effective_task_route', []) or []) or 'none available on this host'}")
    print(f"Conversation mode: {engagement.get('mode', 'adaptive')}")
    print(f"Experience journal: {growth.get('journal', {}).get('records', 0)} records")
    print(f"Semantic memory: {dict(memory.get('counts', {}) or {}).get('semantic', 0)} records")
    print(f"Growth engine: {growth.get('version', 'unknown')}")
    print(f"Realtime phase: {realtime.get('phase', 'unknown')} / anti-echo={'ON' if realtime.get('anti_echo') else 'OFF'}")
    print(f"Attention pending: {dict(realtime.get('attention', {}) or {}).get('pending', 0)}")
    print(f"Compute nodes: {len(nodes.get('nodes', []) or [])}")
    print(f"Retrieval: {retrieval.get('mode', 'unknown')} / vectors={dict(retrieval.get('vector_index', {}) or {}).get('vectors', 0)} / model={retrieval.get('embedding_model', 'n/a')}")
    print(f"Groq key: {yn(os.getenv('GROQ_API_KEY'))}")
    print(f"Gemini key: {yn(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'))}")
    print(f"OpenRouter key: {yn(os.getenv('OPENROUTER_API_KEY'))}")
    print(f"ElevenLabs key: {yn(os.getenv('ELEVENLABS_API_KEY'))}")
    try:
        from mary.mobile.audio import MobileSpeechService
        speech = MobileSpeechService().status()
        print(f"TTS: {'READY' if speech.get('tts', {}).get('enabled') else 'OFF'} / {speech.get('tts', {}).get('provider', 'off')}")
        print(f"STT: {'READY' if speech.get('stt', {}).get('enabled') else 'OFF'} / {speech.get('stt', {}).get('provider', 'off')}")
    except Exception as exc:
        print(f"Voice check: unavailable ({type(exc).__name__})")
    print("Secrets were not displayed.")
    app.close()
    if args.live_providers:
        print("\nLIVE PROVIDERS")
        print("-" * 72)
        return subprocess.call([sys.executable, "-m", "scripts.check_llm_routes", "--live"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
