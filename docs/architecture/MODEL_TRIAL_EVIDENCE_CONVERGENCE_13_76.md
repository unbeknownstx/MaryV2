# MaryV2 13.76 — Model Trial Evidence Convergence

## Goal

Close a remaining self-awareness gap in Mary's model/LoRA experiment path.

Before 13.76, an exact reviewed model experiment could be benchmarked, marked trial-ready, explicitly dispatched on an authorized capability node, and have its terminal outcome appended to `ModelExperimentLedger`. However, the experiment snapshot did not summarize those trial outcomes. `SelfIntrospection` therefore could continue saying that a trial-ready experiment still needed its first bounded trial even after one had completed.

13.76 fixes that by deriving bounded trial evidence from the existing append-only ledger.

## Canonical path

```text
explicit model trial
  -> DeviceTaskBroker
  -> normal capability/task evidence
  -> ModelExperimentLedger trial_dispatched / trial_outcome events
  -> derived trial_evidence
  -> SelfIntrospection
  -> System Fabric / improvement agenda
  -> Desktop / PWA / iPhone
```

No second experiment database, competence store, planner, or model router is introduced.

## Derived trial evidence

`ModelExperimentLedger.snapshot()` now derives, per experiment:

- dispatch count;
- terminal trial attempts;
- completed / failed / rejected / expired counts;
- whether a completed bounded trial has been observed;
- latest structural status, node, provider and model;
- last observed timestamp.

It explicitly states:

- prompt retained: false;
- generated output retained: false;
- quality verified: false.

A completed task is evidence that the bounded experiment ran to completion. It is **not** evidence that the output was good enough for production.

## Self-awareness

For a benchmarked trial-ready experiment:

- with no trial evidence, Mary still asks for a bounded explicit trial;
- with terminal attempts but no completion, Mary asks for a completed bounded trial on the exact authorized experiment node;
- after at least one completed trial, Mary stops asking for a first trial and instead asks for creator-reviewed comparison of the completed trial results before any production-routing decision.

The experiment remains:

- experimental;
- non-authoritative for identity;
- non-authoritative for production routing;
- unable to promote itself.

## Product surfaces

Desktop, PWA and native iPhone now show:

- recorded trial outcomes;
- completed bounded trials.

The legacy mobile web shell remains byte-aligned with the PWA as required by the compatibility contract.

## Authority boundaries

13.76 does not:

- persist held-out prompts;
- persist generated trial text in the experiment ledger;
- infer quality from task completion;
- automatically score a trial;
- automatically promote a model or LoRA;
- modify production routing;
- grant node execution permission.

## Acceptance

13.76 is acceptable when:

1. completed trial lineage changes Mary's next stated evidence need;
2. the derived snapshot contains no prompt or generated-output body;
3. task completion is never labeled as quality verification;
4. the shared System Fabric exposes only content-free trial evidence;
5. Desktop/PWA/iPhone show the same trial counts;
6. deterministic, convergence, system-chain and platform CI remain green.
