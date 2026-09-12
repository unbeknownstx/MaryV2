# Mary Visual System

Mary's UI should feel like a **character space with useful instruments**, not a generic admin dashboard and not a collection of unrelated neon panels.

## Character anchor

Stable visual identity comes from approved Mary references already shipped with the project: vivid red hair, bright blue eyes, purple beanie/shirt, blue outerwear and an anime/game-character silhouette. Generated repository artwork is presentation material—not identity, memory or fictional-lived experience.

Preferred existing presentation assets include:

- `desktop/public/assets/mary-reference.jpeg`
- `desktop/public/assets/gallery/mary-neon-reference-sheet.png`
- `desktop/public/assets/gallery/mary-stream-room-reference.png`
- `desktop/public/assets/gallery/mary-neon-night-manga.png`
- `desktop/public/assets/gallery/mary-gala-reference.png`

Do not replace those with random web imagery merely because it looks futuristic. External images may be design references only unless provenance/license is explicit.

## Color roles

Colors carry meaning consistently across Desktop, SwiftUI and PWA:

| Role | Direction |
|---|---|
| Environment | near-black / deep navy |
| Mary / social / relationship | pink / magenta |
| continuity / mind / depth | violet / purple |
| live capability / system information | cyan / electric blue |
| healthy/available | soft green |
| caution/degraded | amber |
| destructive/error | controlled red |

Avoid using every accent on every card. A screen should have one dominant accent plus state colors.

## Surface hierarchy

1. **Mary stage** — character/presence and current interaction state.
2. **Conversation/work** — what the creator is doing with Mary now.
3. **Context instruments** — continuity, current work, provider/capability health, inbox, study, stream state.
4. **Diagnostics** — deliberately secondary; never overwhelm ordinary use with backend implementation detail.

## Motion

Motion should explain state:

- subtle pulse while connected;
- listening waveform/halo when microphone input is confirmed;
- restrained thinking activity while a turn is running;
- speaking emphasis synchronized to actual playback/viseme data;
- crossfade between approved fallback artwork;
- short panel transitions to preserve spatial continuity.

Avoid permanent high-frequency glow, bouncing, spinning or particle motion. Respect `prefers-reduced-motion` / iOS Reduce Motion. Mary remains fully usable with motion disabled.

## Glass/HUD treatment

Use translucent surfaces sparingly with readable solid fallbacks. Borders are hairlines, not bright boxes around every element. Blur is decorative; contrast must remain sufficient if blur/compositing is unavailable.

Recommended interaction targets:

- touch: at least ~44 pt / px-equivalent effective target;
- pointer: clearly visible hover/focus state;
- keyboard: `:focus-visible` must remain obvious;
- scroll areas: preserve one dominant scroll region rather than nesting many tiny scrollers.

## Responsive behavior

Desktop should adapt rather than require a single minimum monitor width:

- wide: navigation + Mary/work stage + inspector;
- medium: compact navigation + stage; inspector becomes an overlay/drawer or hides noncritical cards;
- narrow/tablet: single primary column with bottom/compact navigation patterns;
- renderer failure never removes chat/work controls.

Native iPhone uses the same information hierarchy without recreating the desktop layout at phone scale. The character stage may be shorter on compact devices, while conversation and push-to-talk stay immediately reachable.

## Text and copy

Surface copy talks about the user's experience, not internal class names. Prefer:

- `Local model available` over `DeviceLlamaCppProvider registered`;
- `Mary is listening` over `VAD confirmed=true`;
- `Portrait mode` over `WebGL renderer unavailable` in primary UI;
- detailed backend diagnostics only inside Runtime/Diagnostics.

## Degraded states are designed states

Supported presentation modes include:

- full VRM/3D;
- portrait/generated-art fallback;
- voice unavailable but text working;
- local node unavailable but cloud route working;
- cloud route unavailable but private/local route working;
- optional integration disconnected.

A degraded optional feature should be visible and understandable, not look like Mary herself failed.
