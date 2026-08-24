# MaryV2 Mobile Companion 12.13 — Build Notes

Base: MaryV2 12.12.2 Natural Conversation Canonical + tested Mobile Companion
surface.

Primary goal: make the phone surface feel like Mary rather than a web page with
browser TTS, without creating a second identity/runtime.

Files added:

- `mary/mobile/audio.py`
- `scripts/check_mobile_voice.py`
- `scripts/rotate_mobile_token.py`
- `tests/mobile/test_mobile_audio_12_13.py`
- `mobile_web/assets/mary-icon-180.png`
- `mobile_web/assets/mary-icon-192.png`
- `MOBILE_12_13_VOICE_SETUP.md`
- `MOBILE_12_13_BUILD_NOTES.md`

Files upgraded:

- `mary/mobile/server.py`
- `mary/mobile/__init__.py`
- `mobile_web/app.js`
- `mobile_web/style.css`
- `mobile_web/index.html`
- `mobile_web/manifest.webmanifest`
- `mobile_web/sw.js`
- `.env.example`
- native bundled `mobile_native/MaryMobile/www/*` synchronized from `mobile_web`

No `.env`, provider keys, or user `data/` are included in the patch package.
