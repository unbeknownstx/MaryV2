# Changelog

## 13.4 — integration candidate — not yet released

- Added natural durable shared-work recall for current-project questions.
- Added trusted ephemeral current-surface grounding for native/desktop/mobile turns.
- Scoped presentation/privacy context per creator device while preserving one canonical Mary.
- Added authenticated Core voice status/synthesis transport backed by the existing voice engine.
- Upgraded the native SwiftUI iPhone client to local-only push-to-talk transcription plus Core-synthesized Mary voice playback.
- Added regression tests for shared-work recall, per-device presentation isolation, current-surface truth, and binary authenticated voice transport.
- Added a bounded current-work projection that joins canonical workspace state with durable shared-work continuity without creating a second project database.
- Unified Mary stage fallback artwork across native iOS, PWA/mobile wrapper, and desktop VRM fallback using the existing generated Mary references.
- Added direct Core `/v1/voice/synthesize` fallback for the PWA/mobile shell when the legacy `/api/tts` route is unavailable.
- Production identity remains 13.3 until live iPhone and full-suite acceptance completes.

## 13.3 — 2026-09-03 — Connected Presence

- Preserved one canonical Mary Core while advancing active runtime identity to 13.3.
- Added explicit Core/session continuity handshakes for surfaces and capability nodes.
- Added Twitch EventSub lifecycle and bounded outbound-chat contracts.
- Added deterministic Twitch/stream response modes: drop, react, chat, speak, both, wait.
- Added typed-chat self-echo suppression and reply-thread preservation.
- Split canonical/display text from deterministic TTS-friendly spoken text.
- Advanced mobile web + native bundled client together and updated iOS app metadata.
- Added offline Mac 13.3 readiness reporting.
- Full deterministic pytest: 1,616 passed, 1 skipped.
- Release hygiene, repository structure, convergence, and mobile/native parity: PASS.

## 0.1.0-alpha — 2026-08-30

- Established weighted creator-authority hierarchy.
- Separated [FC], [DNA], [AI], [PUB], [ALT], [NEG].
- Added identity/model/provider/creator boundaries.
- Synthesized core temperament, humor, care, intelligence, work, relationship, emotion, lived-in and voice-bridge rules.
- Added relationship trust ladder.
- Added 40 behavioral exemplars.
- Added 36 benchmark/evaluation scenarios.
- Added 20 anti-patterns.
- Added bounded runtime selector for existing `personality_context` flow.
- Added provisional voice-intent vectors while deferring final TTS tuning.
