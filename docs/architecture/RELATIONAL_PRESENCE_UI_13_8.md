# MaryV2 13.8 Relational Presence UI

## Product hierarchy

The relational experience should appear as a light, human-facing layer around conversation rather than a settings-heavy relationship simulator.

Primary surfaces should expose:

- current shared activity, when one is active;
- a compact relationship label only when explicitly useful;
- shared-life shortcuts such as Watch, Game, Create, Study, Date and Work;
- private/public presentation state without exposing backend implementation details;
- clear degraded states when voice/avatar/local-node capabilities are unavailable.

## Desktop

Use Mary's stage and conversation as the visual center. Shared activity appears as a small contextual rail/card near the conversation, not as a full dashboard. Runtime/provider/node data remains under diagnostics.

A future desktop-pet mode should reuse the same canonical Core session and relational state. Click/drag/touch reactions are presentation events, not relationship truth by themselves.

## iPhone / PWA

Prefer one-thumb interaction:

- large conversation surface;
- one compact Mary status/presence card;
- horizontal shared-activity shortcuts;
- push-to-talk / voice state with interruption feedback;
- relationship controls under a private settings/detail sheet, not permanently visible.

## Performer / stream mode

The same Mary remains active, but private intimacy is projected down. Public mode may preserve humor, warmth and familiarity while suppressing private romantic callbacks, pet names and sensitive relationship history.

## Accessibility

- minimum 44pt touch targets;
- reduced-motion support;
- no relationship state communicated by color alone;
- visible keyboard focus;
- text labels for avatar-only state changes;
- avoid pulsing/attention-grabbing intimacy indicators designed to induce checking behavior.
