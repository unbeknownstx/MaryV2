# MaryV2 13.83 — Post-Adoption Procedure Evidence

## Goal

Measure what happens after the creator explicitly adopts a reviewed procedure revision.

Earlier slices answer different questions:

- 13.78: what revision came from what predecessor?
- 13.79: is there enough bounded evidence for comparison?
- 13.80: what did the creator explicitly decide?
- 13.82: which creator review admitted this revision into later selected work?
- 13.83: how is the adopted revision actually performing after adoption?

The new evidence remains subordinate to the existing SkillLibrary, CompetenceLedger, plan graph and execution fabric.

## Evidence boundary

Only terminal tasks that carry the approved revision's review ID contribute to post-adoption evidence.

The review record accumulates bounded structural fields:

- attempts;
- successes;
- failures;
- verified successful outcomes;
- bounded task evidence IDs;
- first/last observed timestamps.

Task payloads, prompts, private output and chain-of-thought are not stored.

Evidence IDs are idempotent so replaying the same terminal task cannot inflate the post-adoption counters.

## States

An adopted revision may project:

- `no_post_adoption_evidence` — it has not yet produced a terminal task outcome after adoption;
- `post_adoption_unverified` — outcomes exist but no verified success exists yet;
- `early_post_adoption_evidence` — verified evidence exists but the sample is still small;
- `post_adoption_observed_stable` — at least four outcomes exist, verified success exists and failure pressure remains below the bounded attention threshold;
- `post_adoption_attention` — at least four outcomes exist and observed failure rate is at least 50%.

These are evidence labels, not automatic procedure mutations.

## No automatic rollback

`post_adoption_attention` adds a creator-review item to the existing evidence improvement agenda.

It does not:

- restore the predecessor;
- reject or supersede the adopted revision;
- create another revision automatically;
- bind a different procedure;
- change node/tool permission;
- execute recovery work.

Any new revision or replacement remains an explicit creator-governed decision.

## Flow

```text
creator approval review
  -> approved revision
  -> explicit plan dispatch
  -> terminal task
  -> review ID + task ID
  -> SkillLibrary post-adoption counters
  -> Mary self-awareness / System Fabric
  -> evidence agenda when attention is warranted
```

## Acceptance

13.83 is complete when:

1. only approved revision reviews accept post-adoption evidence;
2. duplicate task evidence IDs are idempotent;
3. a real settled task updates adoption evidence using its review provenance;
4. low evidence requests more evidence rather than claiming stability;
5. repeated post-adoption failures can surface creator attention;
6. the adopted procedure remains unchanged until an explicit creator action changes it;
7. System Fabric exposes the evidence without rollback or execution authority.
