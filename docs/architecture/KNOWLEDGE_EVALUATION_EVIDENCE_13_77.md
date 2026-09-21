# MaryV2 13.77 — Knowledge Evaluation Evidence Convergence

## Goal

Close the remaining gap between deterministic local-knowledge regression and Mary's self-awareness.

Before 13.77, Mary could report whether the local KnowledgeFabric looked structurally ready for regression, but a completed regression run did not become durable bounded evidence. That meant the system could not distinguish:

- never evaluated;
- evaluated and passing on the current substrate;
- evaluated but failing;
- evaluated previously but stale after the substrate changed.

13.77 adds content-free evaluation lineage without creating another knowledge store or truth owner.

## Canonical path

```text
creator-triggered deterministic KnowledgeFabric evaluation
  -> KnowledgeFabricEvaluator
  -> content-free KnowledgeEvaluationEvidenceStore
  -> substrate fingerprint freshness check
  -> SelfIntrospection
  -> System Fabric / improvement agenda
  -> Desktop / PWA / iPhone
```

## Evidence retained

The durable evidence record may retain:

- evaluation timestamp;
- substrate fingerprint;
- case-set fingerprint;
- pass/fail counts;
- bounded per-case IDs and structural metrics;
- citation-coverage numbers;
- whether the latest evaluation passed.

It explicitly does **not** retain:

- query text;
- retrieved snippets;
- source locators;
- source bodies;
- prompts;
- model output.

Changing the KnowledgeFabric substrate fingerprint automatically makes prior evaluation evidence stale.

## Authority boundaries

A passing retrieval evaluation does not:

- make retrieved evidence memory;
- promote retrieved evidence into world truth;
- rebuild stale indexes;
- enable a knowledge pack;
- grant execution permission;
- promote a model or adapter;
- authorize autonomous action.

Evaluation remains deterministic evidence about retrieval quality only.

## CLI

`scripts/evaluate_knowledge_fabric.py` accepts an explicit `--evidence` path. The ordinary detailed output remains available separately; the durable evidence file receives only the bounded content-free projection.

For a canonical Mary runtime, the intended evidence destination is the runtime data path used by `Mary.knowledge_evaluation_evidence`.

## Acceptance

13.77 is complete when:

1. a deterministic regression run can record content-free durable evidence;
2. Mary can tell whether a current passing evaluation exists;
3. substrate changes mark previous evaluation evidence stale;
4. System Fabric projects the same state to all surfaces;
5. queries, snippets and source locators are absent from the durable evidence;
6. no automatic truth promotion, rebuild, permission or execution path is introduced.

## Validation note

The substrate fingerprint includes retrieval-affecting pack state such as enabled/disabled document policy, so changing document activation invalidates prior regression evidence even when index topology is otherwise unchanged.


## Partial substrate owners

Read-only evaluation evidence remains visible when a lightweight/partial knowledge owner cannot produce a full substrate fingerprint. In that case Mary must not claim a current fingerprint match, but she also must not erase already-recorded evaluation history.
