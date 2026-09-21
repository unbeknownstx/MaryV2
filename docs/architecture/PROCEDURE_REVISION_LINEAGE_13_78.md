# MaryV2 13.78 — Procedure Revision Lineage Convergence

## Goal

Make learned-procedure evolution inspectable without creating a second skill store or allowing failure pressure to rewrite an approved procedure automatically.

Mary already had the correct mutation path:

```text
terminal outcomes
  -> SkillLibrary outcome evidence
  -> revision pressure
  -> creator-created revision candidate
  -> explicit creator approval
  -> predecessor superseded
```

13.78 adds the missing read-only lineage layer around that path.

## Revision lineage

`SkillLibrary.revision_lineage()` projects each revision relationship as:

- predecessor procedure ID/version/status;
- candidate procedure ID/version/status;
- creator-authored revision reason;
- structural fields changed;
- whether required capabilities remained unchanged;
- whether required permissions remained unchanged;
- bounded candidate outcome counts, when explicitly observed;
- evidence still needed;
- whether creator approval remains required.

A revision candidate is not described as better merely because it is newer or structurally different.

## Evidence semantics

A candidate with no observed outcomes remains an untested proposal.

A candidate with bounded trial outcomes may be described as observed, but those outcomes still do not:

- approve the candidate;
- widen its capabilities or permissions;
- prove general superiority;
- bind it to an executive plan;
- execute it automatically.

The next comparison/trial layer can therefore attach evidence to a known predecessor/candidate pair instead of inventing another procedural-memory owner.

## Cross-surface convergence

The same lineage is projected through:

- Mary self-introspection;
- System Fabric procedure review;
- the read-only improvement agenda;
- `continuity.skill.status`, consumed by Desktop/PWA/iPhone governance surfaces.

No surface keeps its own procedure version state.

## Approval boundary

`SkillLibrary.approve()` remains the only procedure supersession mutation. Approval is explicit creator action. When an approved revision supersedes its predecessor, the predecessor becomes historical rather than being deleted.

## Acceptance

13.78 is complete when:

1. Mary can identify pending revision candidates and their approved predecessors;
2. version and supersession lineage survives through the existing durable SkillLibrary;
3. structural changes and unchanged authority requirements are visible;
4. missing candidate trial/review evidence appears in the improvement agenda;
5. no candidate is automatically approved, bound, executed, or described as superior.
