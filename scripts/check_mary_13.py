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
    node_rows = list(nodes.get("nodes", []) or [])
    connected_nodes = sum(1 for node in node_rows if bool(dict(node or {}).get("connected")))
    vector_count = int(dict(retrieval.get("vector_index", {}) or {}).get("vectors", 0) or 0)
    vector_state = (
        f"{vector_count} ready"
        if vector_count > 0
        else "not built (structured/lexical recall active)"
    )
    print(f"Compute nodes: {connected_nodes} connected / {len(node_rows)} registered")
    print(
        f"Retrieval: {retrieval.get('mode', 'unknown')} / "
        f"vector index={vector_state} / "
        f"model={retrieval.get('embedding_model', 'n/a')}"
    )
    print(f"Groq key: {yn(os.getenv('GROQ_API_KEY'))}")
    print(f"Gemini key: {yn(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'))}")
    print(f"OpenRouter key: {yn(os.getenv('OPENROUTER_API_KEY'))}")
    print(f"ElevenLabs key: {yn(os.getenv('ELEVENLABS_API_KEY'))}")
    try:
        from mary.mobile.audio import MobileSpeechService
        speech = MobileSpeechService().status()
        tts = dict(speech.get("tts", {}) or {})
        stt = dict(speech.get("stt", {}) or {})
        tts_configured = bool(tts.get("configured", tts.get("enabled", False)))
        tts_ready = bool(tts.get("server_available", tts.get("enabled", False)))
        stt_configured = bool(stt.get("configured", stt.get("enabled", False)))
        stt_ready = bool(stt.get("server_available", stt.get("enabled", False)))
        tts_state = "READY" if tts_ready else ("DEGRADED" if tts_configured else "OFF")
        stt_state = "READY" if stt_ready else ("DEGRADED" if stt_configured else "OFF")
        print(f"TTS: {tts_state} / {tts.get('provider', 'off')}")
        print(f"STT: {stt_state} / {stt.get('provider', 'off')}")
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
