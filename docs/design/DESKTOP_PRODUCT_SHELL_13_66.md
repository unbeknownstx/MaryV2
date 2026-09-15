# MaryV2 13.66 — Desktop Product Shell

13.66 brings the Desktop presentation up to the level of the current backend
architecture without turning the normal companion surface into an engineering
dashboard.

## Design goal

Mary Desktop should feel like a finished character application first and a
powerful system second.

The new shell therefore prioritizes:

- Mary and the active conversation;
- persistent-Core continuity;
- clear local/cloud compute state;
- voice/presence state;
- work, creative, study, focus and stream surfaces;
- diagnostics only when the creator explicitly opens Runtime.

## Visual hierarchy

Wide Desktop uses three primary zones:

1. a compact grouped navigation rail;
2. the main Mary/Talk stage;
3. a secondary context inspector.

The Talk stage itself is split into a readable conversation panel and a Mary
presence/avatar panel. Conversation is no longer placed over a heavily
transparent character scene.

Panels use near-opaque navy surfaces with restrained pink, violet and cyan
state accents. Glass blur is optional decoration rather than the basis for text
contrast.

## Human-facing system rail

The Talk surface projects four display-safe states:

- **Core** — whether the canonical Mary Core link is available;
- **Compute** — whether the bounded local model capability is ready or which
  fallback route is active;
- **Voice** — the active voice presentation path or text-only state;
- **Presence** — idle/listening/transcribing/responding/thinking/speaking.

This projection reads existing runtime/dashboard state. It does not authorize a
provider, grant node permissions, promote a model, or own any Mary state.

## Backend parity

Runtime now includes a Model & Compute Fabric section covering:

- ordinary conversation route;
- general/task route;
- current local-device readiness;
- selected capability node when represented;
- current execution portfolio/revision;
- last provider/model route evidence.

LM Studio, Ollama and llama.cpp are described as replaceable local runtimes
behind the same bounded local-device contract.

## Navigation

The previous long undifferentiated navigation list is grouped into:

- Companion;
- Work & Create;
- Presence;
- System.

All pre-existing workspaces remain available. This is presentation
reorganization, not feature removal.

## Launcher

The launcher now matches the Desktop product language and communicates the
three high-level capabilities that become available after launch:

- persistent Core;
- local + cloud compute;
- voice + avatar presence.

The launcher does not claim those optional runtimes are already active before
Mary starts.

## Transparency policy

Primary reading surfaces intentionally use opaque or near-opaque backgrounds.
Backdrop blur remains only where it adds separation and does not carry the
contrast burden.

In particular:

- chat is an opaque panel;
- workspaces are opaque;
- navigation and inspector rails are opaque;
- launcher copy is opaque;
- message bubbles have clear filled backgrounds;
- system status uses restrained edge emphasis rather than glow around every
  card.

## Responsive behavior

At medium widths the three-column product compresses while retaining Talk and
Mary presence. At compact Desktop widths the inspector is hidden before the
conversation or character stage is sacrificed. Short displays hide secondary
utility cards first.

## Authority boundary

This revision changes presentation only. Canonical Mary Core still owns
identity, memory, relationship, developed self, agency, lifecycle and routing
authority. Models and nodes remain replaceable execution resources.
