# MaryV2 13.33 — Bounded Cognitive Execution

13.33 turns the 13.29–13.32 research-convergence policies into a reusable execution substrate without creating a second Mary, persisting private chain-of-thought, or enabling self-modifying production behavior.

## What changed

### Deliberation execution

`mary.cognition.deliberation.DeliberationExecutor` consumes a `DeliberationPlan` and bounded caller-supplied candidate/verifier callbacks.

Supported strategies remain:

- `single_pass`
- `verify_once`
- `branch_verify`

The executor enforces pass/branch/latency bounds, degrades safely when a verifier is unavailable, and returns only the winning candidate plus structural outcome metadata. Intermediate candidate text is ephemeral working data and is never written to trajectory telemetry.

This gives future production adapters, local open models, and experimental recurrent/latent nodes one Mary-native execution contract instead of each inventing a competing reasoning loop.

### Structural trajectory integration

When a `TrajectoryRecorder` is attached, the executor records only:

- task class;
- selected strategy;
- pass/branch counts;
- verifier score;
- degraded/failure classification;
- provider/tool/token totals supplied as structural metrics;
- latency.

It does not record prompts, candidate text, verifier prose, hidden-state tensors, or private chain-of-thought.

### Experience-informed strategy proposals

`mary.learning.strategy_advisor.StrategyAdvisor` reads content-free trajectory samples and can propose which existing reasoning strategy has performed best for a task class.

The advisor uses conservative sample/margin gates and returns a proposal only. It cannot mutate runtime policy, prompts, identity, memory, providers, or model weights. This is a safe bridge toward later process-reward/RL research: production can collect evidence now without granting automatic learning authority.

### Runtime composition

`PerformanceHardeningBundle` now exposes:

- `mary.deliberation_executor`
- `mary.strategy_advisor`
- the existing shared `mary.trajectory_telemetry`

The executor and advisor are optional helpers beneath canonical Mary. They do not alter startup dependencies or replace `ReasoningEngine`, provider routing, memory ownership, permissions, or the Core authority boundary.

## Promotion path

```text
production task
  -> existing cognitive plan
  -> bounded deliberation executor
  -> structural trajectory evidence
  -> strategy advisor proposal
  -> MaryBench / offline evaluation
  -> creator-approved policy change
```

There is deliberately no arrow from `strategy advisor proposal` directly back into production policy.

## Future research compatibility

This interface is designed so later nodes can implement candidate/verifier callbacks using:

- ordinary cloud/local LLMs;
- Coconut-style continuous latent reasoning;
- Huginn/TRM/MoDr-style recurrent computation;
- LTO/process-reward verifiers;
- vLLM/SGLang inference workers;
- offline AReaL/verl experiments.

Raw latent state remains lab-local. Only bounded final outputs and structural evidence cross back into canonical Mary.

## Deterministic verification

```powershell
python -m pytest tests/cognition/test_deliberation_executor_13_33.py -q
python -m pytest tests/learning/test_strategy_advisor_13_33.py -q
python -m scripts.verify_repository_structure
python -m pytest -q
```

Windows deterministic validation is recorded in `docs/certification/MARYV2_13_33_WINDOWS_VALIDATION_2026-09-13.md`. Mac and Windows should still test the same main commit before any optional runtime is promoted.

The next architecture target is `COMPUTATIONAL_STATE_FABRIC_13_34.md`, which separates Mary's recoverable canonical continuity from rebuildable indexes, warm model/cache state and ephemeral execution state. 13.34 is a design target until code/tests are added.
