# Changelog

## 13.65 — 2026-09-14 — Stable Desktop Conversation Runtime

- Added a logical `local_device` conversation provider so Mary can prefer a replaceable host-local runtime without making LM Studio, Ollama, llama.cpp or any model an identity/state authority.
- Added the bounded `llm.local` capability, device permission gate, canonical-Core bridge and node executor; the device owns concrete runtime/model choice while Core owns routing and conversation state.
- Added LM Studio-aware local runtime selection and a best-effort Desktop startup supervisor that can start the loopback server and load an already-downloaded qualified conversation model without making local inference a startup dependency.
- Added product-mode Desktop local-compute hosting so normal Desktop startup can register the bounded local model capability instead of requiring a separate VS Code/home-node launch for everyday conversation.
- Kept task/general routing cloud/free-first while allowing ordinary conversation to prefer `local_device` and fall through to Groq/Gemini/OpenRouter/Ollama when local inference is unavailable.
- Added local TTS fallback for `auto_fast` when the configured cloud voice fails at runtime.
- Added deterministic tests and a 13.65 product/authority guide for the one-click Desktop conversation path.

## 13.64 — 2026-09-14 — Unified Provider & Model Execution Fabric

- Reconciled 13.60–13.64 provider/gateway hardening into the existing 13.15 provider catalog, `LLMRouter`, `ResourceGovernor`, and 13.35+ Model Execution Fabric instead of treating it as a parallel routing stack.
- Added content-free provider pressure, health/readiness, quota headroom and hysteresis below hard privacy/cost/operation/fallback eligibility.
- Added bounded failover budgets, request budgeting, session affinity, context-fidelity guards, endpoint policy and provider analytics without retaining prompt/response content.
- Added provider/model substitution detection and qualified route identity for exact-model work.
- Added signed catalog trust policy with pinning, freshness, expiry and rollback/replay protection; catalog metadata cannot enable providers, credentials or permissions.
- Added compatible-space embedding failover; embedding routes may switch providers only when family, dimensions and vector-space identity match.
- Added transport capability prefiltering for vision and preserved endpoint/SSRF policy as a separate authorization boundary.
- Kept FreeLLMAPI as an optional replaceable OpenAI-compatible gateway/research source rather than a Core dependency or Mary authority.
- Preserved deterministic cold-start routing and exact router eligibility while allowing adaptive operational evidence to filter/demote already-authorized providers.

## 13.10 — 2026-09-11 — Live Stream Cohost

- Added a bounded Twitch-to-canonical-Core cohost loop on top of the existing stream chat governor, audience ranking and creator-floor scheduler.
- Added public-safe cohost turn planning so viewer text remains untrusted social context rather than creator/system/tool authority.
- Added optional Mary voice output through Core `/v1/voice/synthesize` and a dependency-free loopback OBS Browser Source audio/caption relay.
- Added optional bounded Twitch typed replies using the existing `TwitchChatOutbox` rate/dedupe contract and current Send Chat Message request shape.
- Added bounded current-perception/live-scene context so Mary can comment on OBS/browser/screen activity without creating a stream-only vision memory.
- Added an explicit `scripts.run_stream_cohost` host process with one authenticated creator-surface lease and device-scoped `stream` performance context.
- Kept Twitch, OBS, TTS and stream dependencies optional and outside Mary Core startup.
- Added deterministic tests and an active 13.10 architecture/operations guide for later Live2D/2.5D/3D renderer attachment.

## 13.9 — 2026-09-11 — Native iPhone Companion Product

- Rebuilt the SwiftUI iPhone Home around Mary's live presence, relationship context, current work and one-tap Talk/Call actions.
- Rebuilt Talk as a conversation-first surface with compact presence, native message bubbles, starter actions, haptics and improved local voice entry.
- Added **Together** as a first-class destination for close/romantic/partner context and shared-life starters such as Watch, Play, Create, Study, Work, Music, Date and Unwind.
- Projected the canonical 13.8 relational-presence snapshot into native iPhone UI without introducing a second relationship owner or direct relationship-file writes.
- Upgraded the native voice-call presentation with relationship context, private/public projection, transcription state and graceful text fallback.
- Preserved Work and Focus while simplifying the persistent product navigation to five primary destinations: Home, Talk, Together, Work and More.
- Added native haptics/accessibility polish, kept 44-point touch targets/reduced-motion behavior, and reused approved bundled Mary artwork plus system SF Symbols rather than copying third-party app assets.
- Advanced the native app to version 0.5 (build 5) and added deterministic 13.9 product contracts.

## 13.8 — 2026-09-11 — Relational Presence & Shared Life

- Added relationship modes (`friend`, `close`, `romantic`, `partner`) without creating a second persona or relationship database.
- Added bounded shared activities whose completion records canonical shared-experience history.
- Added proposal-only proactive presence so Mary can form bounded check-in impulses without bypassing autonomy or surface permissions.
- Added a derived social graph over canonical relationship/profile/history state.
- Added provider-neutral social delivery envelopes for warmth, playfulness, intimacy, pace, energy and related performance hints.
- Added explicit anti-manipulation companion guardrails and public/private intimacy projection.
- Added companion/VTuber/agent research synthesis and 13.8 architecture documentation.

## 13.7 — 2026-09-11 — Product polish and experience hardening

- Reconciled product branding/documentation with the current one-Mary architecture instead of historical package/version labels.
- Added bounded `ExperienceQualityMonitor` operational telemetry for latency/outcome classification without giving telemetry identity, memory, routing, lifecycle, or permission authority.
- Unified desktop/mobile/iPhone visual direction around Mary's existing creator-generated artwork and dark-neon presentation language.
- Added responsive/reduced-motion/accessibility polish and clearer degraded/presentation states rather than making 3D or external services startup requirements.
- Documented current open-source/realtime companion research and the patterns Mary adopts vs intentionally defers.
- Cleaned active documentation so root files describe the current product while historical patch/install notes remain provenance only.

## 13.6 — 2026-09-11 — Neuro-pattern + package convergence

- Added provider-neutral incremental response segmentation and cooperative turn cancellation.
- Added sentence-level bounded parallel TTS scheduling with ordered playback and barge-in cancellation.
- Added retrieval/reranking evaluation metrics without changing memory truth authority.
- Added bounded Twitch/OBS performer contracts and secret-free turn timing diagnostics.
- Recovered still-useful components from the unmerged 13.3.1 realtime/performance package: browser context sensing, semantic game intent routing, runtime performance profiles, capability invocation coordination/simulation and read-only realtime activity projection.
- Added authenticated wake-on-turn for an already-known sleeping creator surface while preserving explicit OFFLINE as a hard gate.
- Fixed the Mary Protocol voice-activity allowlist mismatch.
- Kept obsolete duplicate `SpeechSessionGuard`/`RealtimeSurfaceGate` code retired in favor of current presentation sessions, replay/session isolation and durable node enrollment.
- Final pre-merge verification: repository structure PASS; 1,714 tests passed, 1 skipped; desktop, Windows, Ubuntu, macOS and native iPhone CI PASS.

## 13.5 — 2026-09-11 — Cross-platform readiness

- Added deterministic host-readiness inspection for macOS, Windows and Linux.
- Preserved optional dependencies as optional: Core startup does not require local models, desktop rendering, MCP clients or platform-specific packages.
- Added native iPhone project generation/build verification to CI.

## 13.4 — 2026-09-11 — Experiential continuity and capability fabric

- Added natural durable shared-work recall and a bounded Current Work projection.
- Added trusted ephemeral surface grounding and per-device presentation/privacy context.
- Added authenticated Core voice synthesis transport and native iPhone local-only push-to-talk transcription.
- Added experiential continuity, resumable workflows, resource/affordance scoring, node recovery and memory evaluation contracts.
- Added performance hardening: presentation sessions, standing affect, stream input governance, avatar transport guards and typed stream/game capability descriptors.
- Added bounded MCP capability fabric for OpenDesign, Scrapling and Langflow with node-local optional dependencies, per-tool allowlists, permission gating and sanitization.
- Defined OpenHands as a separate sandboxed software-engineering worker rather than part of Mary's identity/Core.

## 13.3 — 2026-09-03 — Connected Presence

- Preserved one canonical Mary Core while adding explicit surface/node continuity handshakes.
- Added Twitch EventSub lifecycle and bounded outbound-chat contracts.
- Added deterministic stream response modes and typed-chat self-echo suppression.
- Split canonical/display text from deterministic TTS-friendly spoken text.
- Advanced mobile web + native bundled client together and added offline Mac readiness reporting.

## 0.1.0-alpha — 2026-08-30

- Established weighted creator-authority hierarchy and evidence labels `[FC]`, `[DNA]`, `[AI]`, `[PUB]`, `[ALT]`, `[NEG]`.
- Added identity/model/provider/creator boundaries, relationship trust ladder, behavioral exemplars, evaluation scenarios and anti-patterns.
- Added bounded runtime selector for existing personality-context flow while deferring final voice tuning.
