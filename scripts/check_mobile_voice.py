"""Show Mary Mobile voice/STT readiness without making a paid synthesis call."""

from __future__ import annotations

from dotenv import load_dotenv

from mary.mobile.audio import MobileSpeechService


def _yes(value: object) -> str:
    return "READY" if bool(value) else "NOT CONFIGURED"


def main() -> None:
    load_dotenv()
    service = MobileSpeechService()
    status = service.status()
    tts = dict(status.get("tts", {}) or {})
    stt = dict(status.get("stt", {}) or {})

    print("MARY MOBILE VOICE")
    print("=" * 72)
    print(
        f"TTS: { _yes(tts.get('server_available')) }  "
        f"provider={tts.get('provider') or 'none'}  "
        f"model={tts.get('model') or 'none'}"
    )
    print(
        f"STT: { _yes(stt.get('server_available')) }  "
        f"provider={stt.get('provider') or 'none'}  "
        f"model={stt.get('model') or 'none'}"
    )
    print()
    print("Mobile playback route: Mary server -> device fallback")
    print("Mobile microphone route: Mary server STT -> browser/native fallback")
    print("This check does not synthesize audio and does not spend TTS credits.")


if __name__ == "__main__":
    main()
