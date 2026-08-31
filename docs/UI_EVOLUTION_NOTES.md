# UI Evolution Notes

The existing mobile interface already has a strong identity: dark navy/purple glass HUDs, magenta/cyan accents, a large Mary portrait, live Core status, conversation modes, and bottom navigation. The desktop already targets a game/virtual-companion shell with VRM, voice, workspaces, ambient audio and runtime diagnostics.

This pass deliberately **layers** on top of those strengths instead of replacing the product with a generic dashboard redesign.

## Mobile priorities

- Keep Mary visually central.
- Keep the composer reachable while the iOS keyboard is open.
- Make state legible without filling the screen with developer data.
- Make Home feel like a companion pulse rather than a control panel.
- Preserve Work/Studio/Command/Focus surfaces while keeping Chat the emotional center.
- Let runtime color/motion shift subtly with represented state, without pretending UI color is emotional truth.

## Desktop priorities

- Increase game-shell atmosphere without reducing text readability.
- Treat VRM/portrait stage as the visual anchor.
- Keep deep system telemetry available but visually subordinate to Mary.
- Use Gallery as a provenance-aware visual library rather than a loose image dump.
- Add ambient motion that can be disabled by `prefers-reduced-motion`.

## Asset strategy

Existing Mary portrait, app icons, VRM, sounds, HUD pieces and backgrounds remain valid. New vector assets are lightweight and generated specifically for the UI layer. The gala image is included as an optional visual study with an explicit non-canon/provenance label.
