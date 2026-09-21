# MaryV2 13.85 — Improvement Proposal Surface Parity

## Goal

Expose the 13.84 proposal-only improvement bridge consistently on every active creator surface without creating a second planner or execution path.

The user-visible flow is now:

```text
shared System Fabric improvement agenda
  -> creator taps Propose next step
  -> canonical Core continuity.improvement.propose
  -> bounded proposal
  -> surface displays proposed objective / next explicit action
  -> nothing else happens automatically
```

## Desktop

Desktop now exposes `proposeImprovement(kind, subject)` through the existing remote-Core bridge.

Evidence agenda cards have a **Propose next step** control. The result is shown as a proposal notification and explicitly states that no plan or task was created.

## PWA / legacy mobile shell

The PWA uses the same mobile bridge method and the legacy bundled mobile shell remains byte-aligned with it.

The proposal button sends only the agenda item's bounded `kind` and `subject`.

## Native iPhone

Native iPhone calls the same Core runtime action directly.

The Advanced workspace stores only the latest ephemeral proposal response and shows:

- proposed objective or next explicit action;
- whether a plan was created;
- whether execution happened.

Both values remain false for this action.

## Authority boundary

13.85 does not add a surface-specific planner.

Desktop, PWA and iPhone all call:

`continuity.improvement.propose`

The canonical Core remains the only authority that derives the proposal from the current improvement agenda.

Surfaces cannot:

- fabricate an agenda item;
- create a plan by merely requesting a proposal;
- grant permission;
- dispatch a device task;
- promote a model;
- rebuild knowledge;
- approve or revise a procedure.

## Acceptance

13.85 is complete when:

1. Desktop, PWA and native iPhone can request the same Core proposal;
2. the bundled legacy mobile shell stays aligned with the PWA;
3. proposal UI clearly states that nothing was created or executed;
4. no new surface-owned planning or persistence layer is introduced.
