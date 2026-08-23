"""Explicit A/B voice lab for MaryV2.

By default this script is offline and only prints the test plan.  Network TTS
calls require ``--synthesize`` so voice comparison can never consume credits as
a side effect of setup, diagnostics or release verification.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import strftime
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional convenience
    load_dotenv = None

from mary.voice import SpeechAudioFormat, VoiceSettings, create_tts_service
from mary.voice.providers import ElevenLabsTextToSpeechProvider


SAMPLES = (
    ("casual", "Yeah, I know. That's actually pretty funny."),
    ("ordinary", "I think the simpler version makes more sense. We can keep the other one as a fallback."),
    ("bright", "Wait, seriously? Okay, that's really cool."),
    ("soft", "I'm here. You don't have to explain everything at once."),
)


def _candidate_ids(cli: list[str]) -> list[str]:
    values = [item.strip() for item in cli if item.strip()]
    if not values:
        values.extend(item.strip() for item in os.getenv("MARY_ELEVENLABS_VOICE_CANDIDATES", "").split(",") if item.strip())
    current = os.getenv("MARY_ELEVENLABS_VOICE_ID", "").strip()
    if current and current not in values:
        values.insert(0, current)
    return values


def _list_account_voices(api_key: str) -> list[dict[str, str]]:
    request = Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key, "Accept": "application/json"},
    )
    with urlopen(request, timeout=15.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    output = []
    for voice in payload.get("voices") or []:
        if isinstance(voice, dict):
            output.append({"name": str(voice.get("name") or "Unnamed"), "voice_id": str(voice.get("voice_id") or "")})
    return output


def main() -> int:
    if load_dotenv is not None:
        load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--voices", nargs="*", default=[], help="Voice IDs to compare. Current Mary voice is included automatically.")
    parser.add_argument("--list-account-voices", action="store_true", help="Explicitly call ElevenLabs to list voices on this account.")
    parser.add_argument("--synthesize", action="store_true", help="Explicitly spend TTS calls to generate the A/B pack.")
    parser.add_argument("--out", default="", help="Output directory for MP3 samples.")
    args = parser.parse_args()

    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if args.list_account_voices:
        if not api_key:
            print("ELEVENLABS_API_KEY is not configured.")
            return 2
        for item in _list_account_voices(api_key):
            print(f"{item['name']}: {item['voice_id']}")
        if not args.synthesize:
            return 0

    voices = _candidate_ids(args.voices)
    print("=" * 76)
    print("MARYV2 VOICE LAB — NATURAL CONVERSATION BASELINE")
    print("=" * 76)
    print("Voices:", ", ".join(voices) if voices else "none configured")
    for label, text in SAMPLES:
        print(f"[{label}] {text}")
    print("Settings: stability=.54 similarity=.82 style=.025 speed=1.00 speaker_boost=true")
    print("Mode:", "SYNTHESIZE (explicit network calls)" if args.synthesize else "PLAN ONLY (zero network calls)")

    if not args.synthesize:
        print("Run again with --synthesize only when you intentionally want to create paid voice samples.")
        return 0
    if not api_key or not voices:
        print("Need ELEVENLABS_API_KEY and at least one voice ID.")
        return 2

    model = os.getenv("MARY_ELEVENLABS_MODEL", "eleven_flash_v2_5").strip() or "eleven_flash_v2_5"
    out = Path(args.out).expanduser() if args.out else Path("runtime_reports") / f"voice-lab-{strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"model": model, "settings": {"stability": .54, "similarity_boost": .82, "style": .025, "speed": 1.0}, "samples": []}

    for voice_index, voice_id in enumerate(voices, start=1):
        provider = ElevenLabsTextToSpeechProvider(api_key=api_key, voice_id=voice_id, model_id=model, timeout=20.0)
        settings = VoiceSettings(
            voice=voice_id,
            speed=1.0,
            output_format=SpeechAudioFormat.MP3,
            metadata={"stability": .54, "similarity_boost": .82, "style": .025, "use_speaker_boost": True},
        )
        service = create_tts_service(provider, settings=settings)
        for label, text in SAMPLES:
            speech = service.synthesize(text, settings=settings)
            if not speech.is_successful:
                print(f"FAILED voice {voice_index} {label}: {speech.status.value}")
                continue
            target = out / f"voice-{voice_index:02d}-{label}.mp3"
            target.write_bytes(speech.audio)
            manifest["samples"].append({"voice_index": voice_index, "voice_id": voice_id, "label": label, "file": target.name, "text": text})
            print("WROTE", target)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Voice lab pack:", out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
