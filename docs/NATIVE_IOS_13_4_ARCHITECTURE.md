# MaryV2 13.4 — Native iPhone Convergence

Status: integration candidate. Canonical Mary identity remains owned by Mary Core.

## Goal

The iPhone app is a first-class native Mary surface that connects directly to the
same Core used by desktop/Mac. It does not depend on Replit, does not embed the
PWA in a WebView, and does not construct another Mary runtime.

The existing PWA remains the visual and interaction reference for the native
phone experience.

## Authority model

```text
Railway / Mary Core
  identity
  relationship
  durable memory
  growth
  workspace
  provider routing
  distributed node registry
  voice synthesis
        |
        | HTTPS Mary Protocol
        v
Native iPhone app
  SwiftUI presentation
  local navigation
  Keychain Core credential
  on-device push-to-talk transcription
  native audio playback
  native lifecycle
  local ephemeral conversation list labels
        |
        +---- Mac / PC capability nodes remain independently connected to Core
```

No iPhone state in this package becomes a second authority for Mary.

## Surface structure

The native app has five stable top-level surfaces matching the mobile PWA:

- Home — Mary presence, current work, Core/node/voice status, presentation context.
- Chat — Mary-first visual stage, Auto/Talk/Deep, conversation selector, text/voice.
- Command — bounded canonical workspace writes.
- Focus — canonical focus session actions plus per-device presentation mode.
- More — native workspace launcher.

Workspaces are navigation destinations, not independent SwiftUI sheets. Settings
and conversation selection share one modal authority (`AppSheet`). This removes
the sheet collision that the earlier SwiftUI prototype produced.

## Direct Core transport

`MaryCoreClient` talks directly to `/v1/*` routes:

- health, state, dashboard, workspace
- turn / conversation
- memory / growth
- voice status + synthesis
- runtime and workspace actions
- creator-surface registration/renewal
- node status/routing
- typed capability preview/dispatch/status

The personal-search workspace dispatches only the existing typed
`personal_search` capability. A connected Mac/PC node still owns local execution
permission. The phone never receives node tokens and cannot execute arbitrary
shell commands.

## Voice

Input:
1. push-to-talk begins on iPhone;
2. Core receives ephemeral realtime listening/transcribing state;
3. recording stays local;
4. Apple on-device speech recognition produces text;
5. temporary audio is deleted;
6. only the transcript is submitted to Core.

Output:
1. Core generates Mary text;
2. Core `/v1/voice/synthesize` produces configured Mary audio;
3. iPhone plays it through AVFoundation;
4. realtime speaking/ended state is reported back to Core.

Provider API keys never live on the phone.

## Stage renderer boundary

`MaryStageView` owns presentation. `MaryStageArtwork` is the current renderer and
loads deterministic Asset Catalog names:

- `MaryPortrait`
- `MaryStreamRoom`
- `MaryManga`
- `MaryReferenceSheet` (gallery)

Raw bundled files remain as a recovery fallback.

A later 2.5D or native 3D/VRM renderer can replace the stage renderer without
changing Core identity, chat transport, memory, navigation, or voice.

## Local-only state

The app may persist:
- Core URL;
- opaque device ID;
- Core credential in Keychain;
- presentation preferences;
- local conversation IDs/labels.

These are client/surface state only. Mary identity and durable continuity remain
Core-owned.

## Acceptance

1. XcodeGen project generation succeeds.
2. Unsigned iPhoneOS compile succeeds.
3. Native convergence pytest passes.
4. Physical iPhone connects directly to Railway Core.
5. Chat text continuity reaches canonical Core.
6. Core TTS plays on iPhone.
7. push-to-talk transcribes locally.
8. Mary stage artwork is visible.
9. Home/Chat/Command/Focus/More all navigate without sheet warnings.
10. Personal Search works when an authorized Mac/PC node is online.
