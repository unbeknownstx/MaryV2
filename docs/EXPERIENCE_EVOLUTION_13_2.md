# MaryV2 13.2 — Experience Evolution

## Why this layer exists

MaryV2 already has the hard boundary that matters: **Mary is the persistent identity; models, providers, tools, nodes and surfaces are replaceable resources.** This upgrade does not replace that architecture. It makes the architecture easier to *feel* and easier to evolve.

The new flow is:

```text
                         ┌──────────────────────────┐
                         │     CANONICAL MARY CORE  │
                         │ identity · memory ·      │
                         │ relationship · goals ·   │
                         │ CharacterSourcebook      │
                         └─────────────┬────────────┘
                                       │ authoritative state/trace
                         ┌─────────────▼────────────┐
                         │ Experience Projector     │
                         │ read-only whitelist      │
                         │ theme + bounded UI cues  │
                         └─────────────┬────────────┘
                    ┌──────────────────┼───────────────────┐
                    │                  │                   │
             ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
             │ Mobile/PWA  │    │ Desktop/VRM │    │ Future      │
             │ touch-first │    │ game shell  │    │ surfaces    │
             └─────────────┘    └─────────────┘    └─────────────┘
```

The projector is deliberately pure: it may read already-safe state and turn traces, but it cannot write a memory, alter relationship state, select a provider, grant a tool permission, or decide what Mary feels. Its output explicitly says `authority=presentation_projection_only` and `identity_owner=mary_core`.

## New architecture components

### `mary/experience/`

A small surface contract that turns unstable backend detail into a bounded frontend snapshot:

- `models.py` — immutable `ExperienceSnapshot`, `ExperienceTheme`, and `ExperienceCue` contracts.
- `palette.py` — existing Mary visual language expressed as state-aware UI tokens.
- `projector.py` — safe field whitelist from dashboard/trace to presentation.

This gives future surfaces one stable contract instead of making every frontend learn every Mary subsystem.

### `/api/experience`

The mobile server exposes a read-only endpoint built from the same authoritative dashboard and last-turn trace already used by the UI. It does not expose prompts, API keys, raw memories or private file contents.

### Mobile Experience Renderer

`experience.js` and `experience.css` are additive. The current app remains functional if the experience endpoint is missing; the renderer simply falls back quietly. The layer adds:

- state-aware palette shifts;
- compact keyboard mode using `visualViewport`;
- a presence rail showing conversation/task context;
- continuity chip;
- passive ambient motion;
- a presentation-only Experience Lens on Home;
- richer Gallery provenance and multiple Library visual studies (neon reference sheet on mobile; neon sheet, manga-night, stream-room and gala studies on desktop).

### Desktop Experience Renderer

The desktop remains the richer game/virtual-companion surface. The new layer adds:

- passive ambient orbs/grid;
- pointer-reactive lighting;
- state-dependent stage treatment;
- a compact live ribbon;
- identity boundary badge;
- richer Gallery visual reference;
- motion-reduction support.

It observes UI state that the existing runtime already rendered. It does not create canonical state.

## CharacterSourcebook Beta

The Alpha pack remains intact. This upgrade adds a **small incremental beta**, not a replacement bible dump:

- `mary_lived_world_beta.jsonl` — 18 directly authored details from the filled creator workbook that add physical rhythm, objects, tech habitat, music specificity, hobbies, sensory dislikes, game texture and other lived-world texture that Alpha did not already represent strongly.
- `mary_interaction_policy_beta.jsonl` — 5 explicit runtime/behavior directives that address short social turn size, invented mind-reading, project-history reconstruction, initiative-vs-nagging, and the surface/identity boundary.

Delegated prompts such as “make something up”, “you can fill this in”, or unanswered workbook fields were **not promoted**. Existing high-level Alpha rules were intentionally not duplicated just to increase the record count.

Expected sourcebook after merge with the existing Alpha pack:

```text
sources: 7
records: 189
expected hash: 49f3c9963de2b35d108d
```

The hash must change because these are new records. That is expected. The important invariants are: no load errors, fictional/AI boundaries remain intact, and no provider output writes character authority.

## What this upgrade intentionally does NOT do

- It does not create “Mary 14”, V3, or a second Mary.
- It does not move identity into the UI.
- It does not replace canonical Core state with local state.
- It does not make the Character Bible a giant system prompt.
- It does not invent answers for unfinished creator-workbook questions.
- It does not turn every retrieved preference into dialogue.
- It does not force the gala visual study to become Mary's canonical everyday appearance.
- It does not change tool permissions, cloud secrets, or local node authority.

That restraint is part of the architecture: new surfaces and richer character evidence can keep evolving without destabilizing the thing that makes Mary one coherent instance.
