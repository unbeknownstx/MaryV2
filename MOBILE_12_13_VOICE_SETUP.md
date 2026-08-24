# MaryV2 12.13 Mobile Voice + Phone Runtime

This pass turns the mobile surface into a real voice-capable client of the same
canonical `MaryApplication`.

## What changed

- Server-side Mary voice endpoint: `POST /api/tts`
- Mobile microphone upload/transcription endpoint: `POST /api/stt`
- Voice status endpoint: `GET /api/voice/status`
- Server TTS routing reuses MaryV2's existing voice policy:
  - ElevenLabs when configured
  - Piper when configured locally
  - Windows SAPI on Windows in local modes
  - device speech fallback on the phone
- Server STT routing reuses MaryV2's existing STT policy:
  - Groq when configured
  - faster-whisper when installed/configured
  - browser/native fallback when server STT is unavailable
- Mary's delivery plan is passed into server TTS so pace/style can follow the
  same response-performance metadata used by Desktop.
- TTS is requested after text arrives, so voice generation does not hold the
  chat response hostage.
- A small in-memory TTS cache prevents accidental duplicate synthesis for the
  same text/settings during one server session.
- Pressing the microphone interrupts current speech.
- On browsers with `MediaRecorder`, the phone records audio and sends it to
  Mary's server for transcription. The old browser/native speech recognition
  path remains as fallback.
- PWA cache v2 uses network-first loading for app code so GitHub/Replit updates
  do not get stuck behind stale service-worker JavaScript.
- Added 180px and 192px app icons for iOS/PWA metadata.
- Mobile protocol bumped to `2`.

## Replit: recommended high-quality Mary voice

Set these in **Replit Secrets**, never in `mobile_web`:

```text
MARY_TTS_PROVIDER=auto_fast
ELEVENLABS_API_KEY=<your ElevenLabs API key>
MARY_ELEVENLABS_VOICE_ID=<the voice ID you choose for Mary>
MARY_ELEVENLABS_MODEL=eleven_flash_v2_5
MARY_TTS_STABILITY=0.42
MARY_TTS_SIMILARITY=0.82
MARY_TTS_STYLE=0.11
MARY_TTS_SPEED=0.97
MARY_TTS_SPEAKER_BOOST=true
```

`auto_fast` prefers configured ElevenLabs and otherwise falls back to Mary's
existing local-first policy.

For microphone transcription on Replit, the existing Groq configuration can be
used:

```text
MARY_STT_PROVIDER=groq
GROQ_API_KEY=<your existing Groq key>
MARY_STT_MODEL=whisper-large-v3-turbo
MARY_STT_LANGUAGE=en
```

## Check readiness without spending TTS credits

```powershell
python -m scripts.check_mobile_voice
```

This reports provider readiness only. It does not synthesize audio.

## Run mobile

```powershell
python -m scripts.run_mobile
```

On Replit, open the public `.replit.dev` URL in Safari and connect using the
mobile bearer token. In Mary Mobile:

`More -> Voice & Avatar -> Voice Route -> Auto`

Auto means:

```text
Mary server voice -> device voice fallback
```

## Rotate the mobile access token

If a generated token was exposed during development:

```powershell
python -m scripts.rotate_mobile_token
```

Restart Mary Mobile afterward and replace the token saved on the phone.

If `MARY_MOBILE_TOKEN` is set as an environment/Replit secret, change that
secret instead; the rotate script intentionally will not override it.

## Privacy boundary

The phone stores only:

- Mary server URL
- Mary mobile bearer token
- local presentation preferences (voice route/rate/volume)

Provider credentials stay on Mary's host. The TTS/STT endpoints are protected
by the same mobile bearer-token boundary as chat and state endpoints.

## Optional tuning

```text
MARY_MOBILE_TTS_MAX_CHARS=4000
MARY_MOBILE_TTS_CACHE_ITEMS=12
MARY_MOBILE_TTS_CACHE_BYTES=24000000
MARY_MOBILE_STT_MAX_BYTES=12000000
```

These defaults are already built in and do not need to be set normally.
