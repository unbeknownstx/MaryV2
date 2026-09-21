# MaryV2 13.82 — Procedure Selection Review Provenance

## Goal

Make the learned-procedure loop auditable after a creator-approved revision enters normal use.

```text
terminal outcomes
  -> revision comparison evidence
  -> explicit creator approve/reject
  -> approved replacement procedure
  -> bounded competence-based future selection
  -> explicit plan dispatch
  -> terminal outcome evidence
```

13.82 carries the creator review ID through that path without turning the review into execution authority.

## Selection behavior

Procedure selection remains exactly as constrained by 13.73:

- the procedure must already be approved;
- it must be demonstrated by verified terminal outcomes;
- it must not be under revision pressure;
- its evidence score must clear the bounded gate;
- ambiguous near-ties are refused;
- selection is ephemeral for one explicit dispatch;
- durable plan binding is unchanged;
- node choice and node-local permission remain separate.

A creator review never boosts the score or bypasses those gates.

## Review provenance

When the selected approved procedure is a reviewed revision, Mary can attach a bounded `creator_review_provenance` record:

- review ID;
- candidate procedure ID;
- predecessor procedure ID;
- approve/reject decision;
- reviewer label;
- review timestamp;
- comparison state at review;
- whether the comparison had reached review-ready evidence.

This is structural provenance only. It contains no task payload, private generated text, prompt, chain-of-thought, or secret.

## Terminal outcome lineage

When an explicitly dispatched task uses a reviewed revision, the process-local task link retains the review ID alongside the plan/step/skill IDs.

At terminal settlement, the review ID is added to the bounded evidence IDs used by:

- `SkillLibrary.record_outcome()`;
- `CompetenceLedger.record()`;
- executive plan step evidence.

That means future audits can trace an observed success/failure back to the creator decision that admitted this revision into normal use.

The review ID does not alter the task result, verification verdict, permission state, or routing authority.

## Authority boundary

13.82 does not:

- auto-approve a revision;
- select an unapproved revision;
- make review evidence count as a successful task outcome;
- grant device execution permission;
- bind a procedure durably to a plan;
- auto-run a plan;
- auto-rollback or supersede a procedure;
- claim a revision is superior.

## Acceptance

13.82 is complete when:

1. an approved reviewed revision can carry its latest creator review provenance into bounded selection;
2. the selector still requires demonstrated non-degrading competence;
3. a dispatched reviewed revision carries the review ID in its process-local continuity link;
4. terminal competence evidence contains both the task ID and review ID;
5. System Fabric declares review provenance as audit-only and non-authoritative;
6. no execution or permission boundary changes.
