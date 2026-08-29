# MaryV2 13.2 Full-Pass Convergence

This package is a single cumulative paste-over source pass built from the authoritative `MaryV2-main current13.2.zip`, the corrected cumulative Stage 14 lineage, Stage 15 creative-production planning, and the subsequent integration fixes in this full pass.

## Architectural rule

Mary remains one canonical runtime. Core owns identity, relationship, memory, character, agency, developed self, conversation state, provider policy, and consequential-state authority. Ecosystem owns non-identity workspace artifacts. Capability nodes are replaceable executors. Presentation surfaces do not become state owners. Explicit training/evaluation evidence does not become identity or memory authority.

## Connected chain

1. **Core / canonical Mary** — `MaryApplication` composes one `Mary`; `MaryCoreService` serializes canonical writes and exposes the shared protocol.
2. **Identity / relationship / memory / developed self** — existing durable owners remain unchanged and feed TurnMind rather than being copied into new production systems.
3. **TurnMind / CharacterMind / reasoning / reflection** — active character stance and bounded context are selected before provider realization; local represented/reflex responses remain available; reflection audits provider output.
4. **Agency / Autonomy** — Agency owns goals, intentions, curiosities and priorities; the existing Agency→Autonomy bridge remains proposal-only and does not grant execution permission.
5. **Presence / realtime / performance** — Presence shares the realtime AttentionBus, can observe canonical workspace changes, and feeds the same Mary turn pipeline. Performance packets remain presentation-only.
6. **Compute fabric** — one LLM router owns provider policy; connected device nodes advertise capabilities; Core can use the existing bounded remote Ollama provider without transferring Mary state to a device.
7. **Training/evaluation** — explicit creator response feedback remains separately persisted. A read-only dataset preview reports SFT/preference/rejected/eval candidate counts; export remains explicit and training is never automatic.
8. **Creative Production Studio** — production projects are now canonical non-identity Ecosystem workspace artifacts. Projects persist plans, character anchors, shots, stages, asset/take metadata and reviews. Production changes publish bounded Presence context without becoming creator-memory facts.
9. **Production capability planning** — canonical projects compile into provider-neutral `video.render`, `voice.synthesize`, and `edit.assemble` jobs. Capability readiness is projected through the existing NodeRegistry. Planning never means execution; unavailable providers remain truthfully unavailable until an adapter/node exists and is permitted.
10. **Cognition awareness** — recent production projects are included in the bounded canonical workspace pulse/context, allowing Mary to discuss current creative work when relevant without promoting the snapshot into memory.
11. **Surfaces** — Core dashboard/state now includes compute, training, production and executable integration-health snapshots. Existing desktop/mobile performer contracts remain intact.
12. **Self-audit** — `mary.runtime.integration_graph` verifies key top-to-bottom reference connections at runtime instead of assuming a module is connected because its file exists.

## Full-pass additions

- `mary/creative/studio.py` — bounded persistent ProductionStudio.
- Production workspace protocol actions: `production.create`, `production.set_stage`, `production.add_asset`, `production.review`.
- Runtime actions: `production.jobs.preview`, `training.dataset.preview`, `integration.status`.
- Production summaries in canonical workspace, companion pulse and cognition-safe workspace context.
- Core state/dashboard projections for production, training and integration health.
- Runtime integration graph with required-vs-optional connection semantics.
- Training dataset preview is read-only and explicit-feedback-only.
- Updated stale release verifiers so the deterministic release gate validates current 13.2 contracts rather than old prompt/version literals.

## Deliberate boundaries / still-open capability paths

This pass makes the architecture and internal pipeline coherent; it does **not** fake external renderer availability. A real image/video provider, editor, music/SFX system, social publishing adapter, Twitch/OBS adapter, or local generative-media node must advertise/implement its actual capability before production jobs become executable. Consequential external actions remain approval-gated. True model fine-tuning remains a later explicit training operation using curated exported evidence, not ordinary conversation logs.

## Verification performed on reconstructed full tree

- Full pytest: **1299 passed, 1 skipped, 0 failed**.
- Deterministic/offline release gate: **PASSED**.
- System diagnostics: **61/61 PASS**, 0 warnings, 0 failures.
- Python compile: PASS.
- Desktop JavaScript syntax: PASS.
- Mobile JavaScript syntax: PASS.
- Mobile web/native app and style synchronization: PASS.
- Checked-in `data/` tree hash remained byte-for-byte unchanged from the authoritative baseline.

## Installation

Paste this cumulative package over the current MaryV2 project root and allow matching source files to replace. Do not delete or replace your `.env` or live `data/` directory. Then run `VERIFY_FULL_PASS_WINDOWS.ps1` from the repository root on Windows.
