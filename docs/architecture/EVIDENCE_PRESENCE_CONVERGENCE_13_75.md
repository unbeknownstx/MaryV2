# MaryV2 13.75 — Evidence / Presence Convergence

## Goal

Turn the systems added and connected in 13.73–13.74 into one readable improvement loop across every Mary surface:

```text
task outcomes / retrieval health / procedure evidence / model trials
    -> existing canonical evidence owners
    -> read-only improvement agenda
    -> Desktop / PWA / iPhone
    -> explicit creator choice or future bounded task
```

The agenda is not an agent, scheduler, permission owner, memory store or autonomous planner.

## Evidence agenda

`mary.runtime.system_fabric` now combines existing evidence gaps from:

- live capability self-awareness;
- `CompetenceLedger` evidence;
- approved procedure evidence and revision pressure;
- `KnowledgeFabric` freshness / deterministic evaluation readiness;
- model / adapter experiment evidence.

Each item names the subject, current evidence state and the evidence still needed. Recovery items are surfaced before ordinary evidence gaps, but no score or recommendation can grant execution permission.

The agenda explicitly reports:

- `automatic_execution = false`;
- `automatic_permission = false`;
- `automatic_model_promotion = false`.

## LiveScene convergence

Riko-style embodiment becomes more useful when the body is visibly connected to Mary's current situation instead of merely knowing static renderer capabilities.

13.75 therefore projects a bounded structural summary from the existing ephemeral `LiveScene` into the embodiment contract:

- companion/stream scene mode;
- current realtime phase;
- current floor owner;
- participant count;
- whether an activity/project/workspace/asset/target/goal is present;
- recent event count.

Scene content itself is deliberately omitted from the shared System Fabric. The projection exposes that situational context exists without turning private current-work text into general diagnostics.

`LiveScene` remains process-local and non-durable.

## Surface convergence

### Desktop

The System Fabric workspace now exposes:

- authorized vs demonstrated capability counts;
- evidence gap / recovery counts;
- deterministic knowledge-regression readiness;
- the bounded improvement agenda;
- current embodiment / LiveScene state.

This pass also fixes a pre-existing runtime defect where the Fabric view referenced `authorizedCaps` and `demonstratedCaps` without defining them in `renderFabric()`.

### PWA / compatibility web shell

PWA shows the same improvement and embodiment panels. The legacy `mobile_native` web shell remains byte-aligned with `mobile_web` because current compatibility tests intentionally require parity.

### Native iPhone

The Advanced workspace now reads the canonical `system_fabric` projection rather than presenting a separate backend diagnostic model. Knowledge also exposes deterministic evaluation readiness, while Model Lab receives the same capability contract used elsewhere.

## Authority boundaries

13.75 still cannot:

- execute an improvement item automatically;
- grant a node permission;
- rewrite a learned procedure;
- rebuild a knowledge source merely because it is stale;
- promote retrieved evidence into memory or world truth;
- promote a model / LoRA into production;
- persist LiveScene as identity, relationship, emotion or memory;
- let a renderer/body become Mary.

## Acceptance

The slice is complete when:

1. all three active product surfaces read the same canonical evidence agenda;
2. current situational presence is visible without private scene-content leakage;
3. capability advertisement, demonstrated competence and permission remain separate;
4. knowledge evaluation readiness refuses a clean state when source derivatives are stale;
5. no automatic execution or model promotion path is introduced;
6. full convergence, system-chain, platform and deterministic CI gates remain green.
