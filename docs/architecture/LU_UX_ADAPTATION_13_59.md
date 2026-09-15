# MaryV2 13.59 — LU-inspired workspace UX

MaryV2 mined Locally Uncensored for interaction patterns, not product identity or source code. The useful UX lesson adopted here is fast navigation across a growing tool/workspace surface while preserving clear grouping and keyboard accessibility.

## Adaptation

Mary's existing workspace sheet remains the canonical navigation surface and keeps its Companion / Work / Create-Media / System grouping. A presentation-only quick switcher now filters those existing controls by name and description.

- Search is local DOM filtering only; it sends no request and stores no query.
- `Cmd/Ctrl+K` opens/focuses the workspace search on keyboard-equipped surfaces.
- Arrow keys move the active result and Enter activates the existing workspace button.
- `/` focuses search while the workspace sheet is already open.
- Escape clears a query before normal dialog dismissal.
- Empty groups collapse while filtering and an explicit no-match state is shown.
- The feature is bundled in the PWA offline shell and mirrored exactly into the native iOS web bundle.

This intentionally does **not** copy LU's full desktop shell, model-management UI, branding, or information architecture. Mary remains companion-first: backend/provider detail stays in Runtime/System views rather than crowding the primary conversation surface.

## Authority

`mobile_web/ux-13-59.js` is presentation only. It calls existing `data-open` controls and owns no Mary state, memory, permissions, routing, provider selection, task execution, or persistence. `mobile_web/` remains source of truth; `mobile_native/MaryMobile/www/` is the generated native mirror.
