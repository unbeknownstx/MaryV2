"""Deterministic verification for MaryV2 Mobile 12.13."""

from __future__ import annotations

from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parents[1]


def check(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL  {label}")
    print(f"PASS  {label}")


def main() -> None:
    print("=" * 72)
    print("MARYV2 MOBILE 12.13 VERIFICATION")
    print("=" * 72)

    required = [
        "mary/mobile/audio.py",
        "mary/mobile/server.py",
        "scripts/run_mobile.py",
        "scripts/check_mobile_voice.py",
        "scripts/rotate_mobile_token.py",
        "mobile_web/index.html",
        "mobile_web/style.css",
        "mobile_web/app.js",
        "mobile_web/sw.js",
        "mobile_web/manifest.webmanifest",
        "mobile_web/assets/mary-reference.jpeg",
        "mobile_web/assets/mary-icon.png",
        "mobile_web/assets/mary-icon-192.png",
        "mobile_web/assets/mary-icon-180.png",
    ]
    for relative in required:
        check((ROOT / relative).is_file(), f"{relative} exists")

    py_compile.compile(str(ROOT / "mary/mobile/audio.py"), doraise=True)
    py_compile.compile(str(ROOT / "mary/mobile/server.py"), doraise=True)
    check(True, "mobile Python compiles")

    server = (ROOT / "mary/mobile/server.py").read_text(encoding="utf-8")
    app = (ROOT / "mobile_web/app.js").read_text(encoding="utf-8")
    worker = (ROOT / "mobile_web/sw.js").read_text(encoding="utf-8")
    env = (ROOT / ".env.example").read_text(encoding="utf-8")

    check(('MOBILE_PROTOCOL_VERSION = "2"' in server or 'MOBILE_PROTOCOL_VERSION = "3"' in server or 'MOBILE_PROTOCOL_VERSION = "4"' in server), "mobile protocol preserves 12.13+ contract")
    check('path == "/api/tts"' in server, "server TTS endpoint")
    check('path == "/api/stt"' in server, "server STT endpoint")
    check("/api/tts" in app and "/api/stt" in app, "phone uses server audio routes")
    check("server" in app and "device" in app and "voiceMode" in app, "voice routing controls")
    check(("maryv2-mobile-shell-v2" in worker or "maryv2-mobile-shell-v13" in worker or "maryv2-mobile-shell-v13-1" in worker) and "networkFirst" in worker, "PWA update-safe cache")
    check("MARY_MOBILE_TTS_MAX_CHARS" in env, "mobile voice tuning documented in env template")

    native = ROOT / "mobile_native/MaryMobile/www"
    check((native / "app.js").read_bytes() == (ROOT / "mobile_web/app.js").read_bytes(), "native web bundle synchronized")

    print("=" * 72)
    print("MOBILE 12.13 VERIFIED")


if __name__ == "__main__":
    main()
