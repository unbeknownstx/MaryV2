# MaryV2 13.79 — Procedure Comparison Evidence

## Goal

Close the next learned-procedure loop after 13.78 revision lineage.

13.78 made predecessor/candidate relationships inspectable. 13.79 adds a bounded comparison state so Mary can tell whether the two procedure versions have enough verified operational evidence for a meaningful creator review.

This remains evidence only.

```text
terminal task outcomes
  -> CompetenceLedger
  -> approved predecessor / revision candidate evidence
  -> bounded comparison readiness
  -> creator review
  -> explicit creator approval or rejection
```

No comparison result approves, binds, executes, or widens a procedure.

## Comparison states

A revision lineage row may project:

- `unavailable` — no competence evidence owner is connected;
- `authority_changed` — capability or permission requirements differ, so ordinary quality comparison is insufficient;
- `candidate_unverified` — the candidate has no verified successful terminal outcome;
- `predecessor_unverified` — the predecessor lacks verified success evidence;
- `insufficient_evidence` — both have verified evidence but the sample/evidence strength is still too thin;
- `review_ready` — both versions have enough bounded verified operational evidence for creator comparison.

`review_ready` is not `better`, `approved`, or `production-ready`.

## Evidence used

The comparison reuses `CompetenceLedger.skill_summary()` and therefore sees only structural operational evidence:

- attempts;
- successes/failures;
- verified successful outcomes;
- bounded posterior reliability;
- evidence strength;
- last observed status/time.

It does not retain task payloads, prompts, chain-of-thought, or private output.

## Authority compatibility

A normal comparison is allowed only when the revision retains the predecessor's required capabilities and permissions. If those authority requirements change, the comparison state becomes `authority_changed` and explicit creator review is required before interpreting the revision.

## Surface convergence

The comparison lives inside the existing `SkillLibrary.revision_lineage()` projection when a `CompetenceLedger` is supplied.

That same evidence flows through:

- Mary self-introspection;
- `continuity.skill.status`;
- System Fabric procedure review;
- the evidence improvement agenda;
- Desktop/PWA/iPhone consumers of those shared Core projections.

No surface owns a separate score or revision decision.

## Improvement agenda

When a comparison becomes `review_ready`, the read-only improvement agenda marks it as creator `review` rather than another trial request.

It still reports:

- no superiority claim;
- no automatic approval;
- no automatic execution;
- no permission change.

## Acceptance

13.79 is complete when:

1. unverified candidates cannot become comparison-ready;
2. weak evidence remains `insufficient_evidence`;
3. authority-changing revisions cannot be treated as ordinary quality comparisons;
4. sufficiently evidenced predecessor/candidate pairs become `review_ready`;
5. Mary can explain that state without claiming the revision is superior;
6. creator approval remains the only mutation that supersedes the predecessor.
