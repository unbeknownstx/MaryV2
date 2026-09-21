# MaryV2 13.81 — Procedure Review Surface Parity

## Goal

Make 13.80 creator revision decisions visible on every first-class creator surface without creating any surface-owned governance state.

The source of truth remains:

```text
SkillLibrary.review_revision()
  -> continuity.skill.status
  -> SelfIntrospection / System Fabric
  -> Desktop / PWA / legacy mobile shell / native iPhone
```

## Surface behavior

Desktop, PWA and native iPhone now show:

- total recorded revision decisions;
- recent creator approve/reject decisions;
- candidate revision version/ID;
- comparison state captured at decision time;
- reviewer label;
- optional creator reason.

The legacy mobile web shell remains aligned with the PWA contract.

## Authority boundary

These views are audit/presentation only.

They do not:

- compute a new comparison score;
- decide whether a revision is better;
- approve or reject automatically;
- grant tool/node/model permission;
- bind a procedure to a plan;
- execute a procedure.

The surface simply renders the bounded decision evidence already owned by Mary Core.

## Acceptance

13.81 is complete when:

1. Desktop shows recent revision decision history from System Fabric;
2. PWA and legacy mobile shell consume the same projection;
3. native iPhone shows the same creator decision evidence in Procedures;
4. all surfaces state or preserve the explicit-creator authority boundary;
5. no separate surface persistence is introduced.
