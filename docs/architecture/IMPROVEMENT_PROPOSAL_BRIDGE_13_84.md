# MaryV2 13.84 — Improvement Evidence Proposal Bridge

## Goal

Close the next gap in the intelligence convergence loop without granting Mary new execution authority:

```text
observed evidence gap
  -> read-only improvement agenda
  -> deterministic proposal
  -> explicit creator choice
  -> existing typed plan/review/trial action
```

13.84 does **not** create or run a plan automatically. It only translates an existing evidence-gap item into a bounded proposal that tells a surface what explicit action would be appropriate next.

## Runtime action

`continuity.improvement.propose`

Inputs:

- `kind` — the existing improvement-agenda item kind;
- `subject` — the exact agenda subject.

The action reads the current shared System Fabric and refuses subjects that are not present in the current agenda.

## Proposal routing

The bridge maps current evidence to existing owners:

- capability evidence gap → draft explicit plan with a typed capability step;
- procedure evidence gap → procedure-evidence plan draft;
- reviewed procedure revision → existing creator review/status path;
- trial-ready model experiment → existing explicit model experiment dispatch path;
- knowledge substrate attention → creator-reviewed maintenance plan draft.

The bridge does not invent another planner or workflow engine.

## Plan draft boundary

A plan proposal contains:

- objective;
- priority;
- tags;
- zero untyped plan-create steps;
- explicit `step_additions` containing capability and verification requirements.

Keeping `steps` empty matters because `continuity.plan.create` cannot attach typed capability requirements. A surface that accepts a proposal must explicitly create the plan and then add the typed steps through `continuity.plan.add_step`.

## Authority

Every proposal reports:

- `plan_created = false`;
- `execution_performed = false`;
- `permission_granted = false`;
- `model_promoted = false`;
- `automatic_action = false`.

Node-local permission, creator approvals, model promotion, knowledge maintenance and task dispatch remain owned by their existing systems.

## Acceptance

13.84 is complete when:

1. only a live improvement-agenda item can be proposed;
2. a capability gap produces a correctly typed step draft;
3. review-ready revisions route to explicit creator review rather than execution;
4. trial-ready experiments route to the existing explicit trial action without promotion;
5. no proposal mutates plan, procedure, knowledge, permission or model state.
