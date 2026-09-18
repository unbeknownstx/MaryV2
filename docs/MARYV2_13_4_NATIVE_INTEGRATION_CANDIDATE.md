# MaryV2 13.4 Native Integration Candidate

Status: **historical integration candidate**. Current authority and product status are defined by `MARY_ROOT.md` and the system registry; the Core `13.3` architecture value is retained as a compatibility/handshake identifier rather than a product-freshness label.

## Invariants

- One canonical Mary Core owns identity, relationship, memory, development, agency, and durable continuity.
- Native iOS, desktop, PWA, CLI, and capability nodes are replaceable surfaces/capabilities, never separate Mary identities.
- Provider credentials remain on Core/authorized hosts. Native iOS stores only the Core credential in Keychain.
- Raw microphone audio stays on the originating iPhone for on-device transcription.
- Public presentation modes retain the existing fail-closed privacy guard.

## Integrated candidate changes

### Shared-work continuity

Natural questions such as `What are we working on?`, `What have we been working on today?`, and `Where are we with MaryV2?` route to Mary's durable shared-work relationship history rather than free-form model inference.

### Runtime surface truth

Each turn carries a bounded ephemeral current-surface projection derived from trusted protocol metadata. It is context only and cannot mutate identity or memory. The dialogue layer is explicitly instructed to prefer this current runtime fact over stale historical device memories.

### Per-device presentation context

Private/Casual/Focus/Stream/Performance is scoped by creator device at Core. The canonical turn writer lock temporarily applies the requesting device's presentation mode while the turn executes, then restores the base projection. This allows, for example, a private iPhone creator surface and a public stream surface to coexist without creating another Mary.

### Canonical Core voice output

Core exposes authenticated `/v1/voice/status` and `/v1/voice/synthesize` routes backed by the existing `MobileSpeechService`. ElevenLabs or another configured voice provider remains server-side; provider keys are never sent to iOS.

### Native iOS voice

The SwiftUI app keeps microphone audio local, records a bounded push-to-talk file, uses required on-device Apple speech recognition, deletes the temporary recording, sends only the transcript through the canonical turn API, then prefers Mary's Core-synthesized response audio and falls back to iPhone system speech when Core TTS is unavailable.

### Repository hygiene

Installer-created iOS backup directories are ignored, and accidental zero-byte shell-paste artifacts are removed from source.

## Acceptance gates

1. Full Python suite passes in the configured Mary development environment.
2. Native iOS project regenerates with XcodeGen and builds for `iphoneos` without code-signing.
3. Physical iPhone confirms canonical text continuity, Core voice playback when available, and device-speech fallback when Core TTS is degraded.
4. `What are we working on?` recalls current shared-work continuity without LLM guessing.
5. iPhone Private and another device Stream remain isolated at the presentation/privacy layer.
6. Provider secrets never appear in iOS source, app storage outside Keychain Core credential, response payloads, or logs.

These were the acceptance gates for the 13.4 candidate milestone; current release/product state is tracked by the active registry and current test gates.

## Cohesive surface convergence additions

### Current-work projection

Mary now derives a bounded `current_work` projection from the existing canonical workspace plus durable creator-owned shared-work relationship history. It is injected into turn runtime context and exposed to remote-safe workspace surfaces. It is **not** a new memory store, identity authority, project database, or execution authority. This closes the gap where the UI could show the correct shared-work event while free-form dialogue guessed an older project state.

### Unified Mary stage fallback

Native iOS uses local generated Mary artwork for its stage until a native live-VRM renderer is implemented. Desktop keeps the live VRM as first choice and crossfades through the same local Mary artwork when the VRM cannot load. The PWA/mobile prototype uses the same art set, keeping visual identity consistent without making generated art canonical character evidence.

### Mobile voice compatibility

The PWA/mobile shell still prefers its legacy `/api/tts` route when served through `MaryMobileServer`, but now safely falls back to authenticated Core `/v1/voice/synthesize`. Native SwiftUI talks directly to the Core voice route and uses iPhone system speech only as a presentation fallback. Provider credentials remain server-side in both cases.
