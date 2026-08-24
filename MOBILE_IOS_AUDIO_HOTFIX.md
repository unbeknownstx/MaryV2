# MaryV2 Mobile 12.13.1 iOS Browser Audio Hotfix

This patch fixes server TTS that returns HTTP 200 but does not audibly play on iPhone browsers.

Changes:
- Primes/unlocks both an HTMLAudioElement and Web Audio during a user gesture.
- Plays server MP3 through a Blob URL + HTMLAudioElement first (better on iOS browsers).
- Falls back to Web Audio decoding if media-element playback fails.
- Keeps device TTS as fallback only in Auto mode.
- In Server-only mode, reports a browser playback block instead of silently falling back.
- Revokes Blob URLs and stops prior playback on interruption.
- Bumps PWA cache to maryv2-mobile-shell-v3.
- Syncs the native iPhone bundled web copy.

Verification:
- node --check mobile_web/app.js: PASS
- pytest tests/mobile tests/voice -q: 35 passed
