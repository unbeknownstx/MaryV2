# MaryV2 12.11 — Fast Dialogue + Connected Presence

This release is an in-place source upgrade for the canonical `MaryV2` repository. Preserve the creator's existing `.env` and persistent state.

## Windows setup

```powershell
cd C:\Users\Melvin\Documents\GitHub\MaryV2
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

## Recommended live conversation configuration

```env
MARY_LLM_CONVERSATION_ORDER=groq,gemini,openrouter,ollama
MARY_GROQ_CONVERSATION_MODEL=llama-3.1-8b-instant
MARY_TTS_PROVIDER=elevenlabs
MARY_ELEVENLABS_MODEL=eleven_flash_v2_5
```

`MARY_GROQ_MODEL` remains available separately for task/general Groq work. Paid OpenAI remains the explicit expert route and is not added to normal conversation routing.

## Optional connected features

YouTube public metadata search:

```env
MARY_YOUTUBE_ENABLED=true
YOUTUBE_API_KEY=...
```

Local read-only Presence WebSocket:

```env
MARY_WEBSOCKET_ENABLED=true
MARY_WEBSOCKET_HOST=127.0.0.1
MARY_WEBSOCKET_PORT=8765
# Strongly recommended before any non-loopback design:
MARY_WEBSOCKET_TOKEN=...
```

Neither feature is required for Mary to launch.

## Tests

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test_full.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test_release.ps1
```
