# MaryV2 13.2 — Web / Replit Convergence Pass

This pass turns the Replit/mobile web surface into a first-class client of the canonical Mary Core without moving identity or durable state into the browser.

## Added

- Browser-managed bounded conversation IDs with stable cross-device presets:
  - `creator-primary`
  - `project-maryv2`
  - `project-unbeknownst`
  - `study-primary`
- Chat transport now carries `conversation_id` and `voice_input` to Core.
- Mobile runtime exposes the active conversation ID without treating it as identity state.
- Core display hints expose a **bounded** dialogue-plan subset for developer inspection.
- Runtime UI shows TurnMind → Dialogue drive/stance/tone/pacing/question/initiative guidance from the latest turn.
- Runtime UI shows connected device nodes and their advertised capabilities.
- Remote mobile PersonalSearch now uses the typed Core device-task broker and returns device-sanitized results.
- Search UI displays selected-device execution state while keeping absolute roots private.
- Canonical `mobile_web` ↔ native iOS bundle synchronization is automated and testable.
- Replit self-check verifies configuration presence and read-only Core connectivity without printing secrets.
- PWA cache/version text updated to the 13.2 unified-client baseline.

## Boundaries preserved

- Conversation IDs isolate only bounded short dialogue history.
- Device nodes do not own character identity, memory, relationship, growth or canonical workspace state.
- The web client cannot execute generic shell commands.
- `personal_search` remains a typed task and is still subject to the selected device's local permission policy.
- TurnMind diagnostics are derived/context-only and do not become memory or personality.
- `mobile_web/` remains the source of truth; native `www/` is generated.
