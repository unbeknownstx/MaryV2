# MaryV2 mobile surface convergence — 13.4 candidate

Production identity remains **13.3 Connected Presence** until live acceptance passes.

## One Mary, several surfaces

- Railway/Core remains the only authority for Mary identity, relationship, memory, development, agency and shared durable continuity.
- `ios/MaryV2iOS` is the long-term native iPhone client.
- `mobile_web` remains the PWA/design/testing surface.
- `mobile_native/MaryMobile` remains a compatibility wrapper around the PWA source while migration completes; its web bundle is kept byte-for-byte synchronized by tests.
- Desktop remains the richest local capability surface and attempts the live VRM first.

None of these surfaces is another Mary.

## Presentation convergence

The same local Mary artwork is used as a fallback set across surfaces:

1. `mary-reference.jpeg`
2. `mary-stream-room-reference.png`
3. `mary-neon-night-manga.png`
4. `mary-neon-reference-sheet.png` (native/reference gallery)

Desktop: live `MaryCosma.vrm` first, generated-art crossfade only if VRM presentation is unavailable.

Native iOS: generated-art stage until a native VRM renderer is implemented.

PWA/compatibility mobile: generated-art stage with reduced-motion handling.

Generated visuals are presentation/reference assets only. They never become identity, memory, relationship or development evidence automatically.

## Current work convergence

`current_work` is a read-only derived projection built from:

- canonical workspace state (focus, command, production), and
- durable creator-owned shared-work relationship history.

The projection is available to conversation context and mobile/workspace status so the answer to "what are we working on?" and the app's current-work card use the same evidence. It is not a second project database.

## Voice convergence

Native iOS:

`Core /v1/voice/synthesize -> rendered Mary audio -> iPhone playback`

PWA/compatibility client:

`/api/tts` when served by MaryMobileServer, otherwise authenticated `/v1/voice/synthesize` on Core.

Provider secrets stay on Core/authorized hosts. Native microphone raw audio remains local on iPhone for on-device transcription; only text is sent to canonical Core.
