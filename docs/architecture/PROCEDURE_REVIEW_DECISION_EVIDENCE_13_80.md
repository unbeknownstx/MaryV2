# MaryV2 13.80 — Procedure Review Decision Evidence

## Goal

Close the creator-review edge that 13.79 intentionally left open.

13.79 can prove that a predecessor/revision pair is ready for human review. 13.80 makes the creator's explicit decision auditable without allowing comparison evidence to become approval authority.

```text
terminal outcome evidence
  -> bounded predecessor/candidate comparison
  -> creator review
  -> explicit approve/reject
  -> content-free decision snapshot
  -> revision lineage / self-awareness / System Fabric
```

## Authority rule

The comparison never decides.

Only an explicit creator `continuity.skill.approve` or `continuity.skill.reject` mutates revision state. For revision candidates those existing actions now route through `SkillLibrary.review_revision()`, which records the evidence visible at decision time.

Ordinary non-revision skill approval/rejection remains unchanged.

## Recorded review evidence

Each revision review stores only bounded structural evidence:

- candidate/predecessor IDs and versions;
- approve/reject decision;
- reviewer identity label and timestamp;
- optional bounded creator reason;
- comparison state and review-ready flag;
- shared capability;
- bounded competence summaries;
- reliability delta when comparison-ready;
- remaining evidence-needed labels.

It does not store task payloads, prompts, private generated text, chain-of-thought, or tool secrets.

## Decision semantics

A creator may explicitly decide even when comparison evidence is incomplete.

That is intentional: evidence informs the creator but does not outrank creator authority. The audit record therefore preserves whether the decision occurred from `review_ready`, `insufficient_evidence`, `unavailable`, or another comparison state.

Approval of a revision supersedes the predecessor exactly as before. Rejection leaves the predecessor approved.

## Projection

Decision evidence is exposed through:

- `SkillLibrary.revision_review_history()`;
- `SkillLibrary.revision_lineage().latest_review`;
- `continuity.skill.status`;
- Mary self-introspection;
- System Fabric procedure review.

Surfaces remain read-only consumers of this projection.

## Acceptance

13.80 is complete when:

1. revision approval records the comparison snapshot before superseding the predecessor;
2. revision rejection records the snapshot without superseding the predecessor;
3. comparison evidence never sets the decision automatically;
4. ordinary skill approval remains backward compatible;
5. Mary can inspect how many revision decisions exist;
6. System Fabric can project those decisions without gaining approval or execution authority.
