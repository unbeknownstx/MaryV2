# MaryV2 13.29–13.32 — Cognitive Research Convergence

This pass converts useful mechanisms from current agent-memory, latent-reasoning,
realtime-voice, distributed-inference, evaluation and reinforcement-learning
research into bounded MaryV2 architecture. It deliberately does **not** install
another Mary, another memory authority, a self-modifying production loop, or a
framework-owned agent runtime.

The governing invariant remains:

> **Mary is one canonical computational character. Models, reasoning strategies,
> verifiers, memory projections, transports, training systems and machines are
> resources beneath Mary rather than alternate identities.**

## 13.29 — Adaptive deliberation

`mary.cognition.deliberation.DeliberationGovernor` turns the existing 13.17
cognitive-character plan into a bounded test-time-compute plan.

Strategies:

- `single_pass` for ordinary/relational/direct turns;
- `verify_once` when uncertainty or task depth merits one verifier pass;
- `branch_verify` for deep non-realtime work where alternatives are valuable.

The policy carries hard limits for passes, branches, confidence and latency.
Realtime work is automatically compressed so a deep plan cannot create long
voice dead-air.

The workspace contract is structural only:

```text
facts
constraints
unknowns
candidate_actions
confidence
```

Private chain-of-thought is neither required nor exposed. The policy explicitly
marks private-reasoning persistence and exposure as false. If a model uses
hidden reasoning internally, Mary consumes only bounded outputs, verifier
signals and final task evidence.

`CharacterRuntimeCoordinator` now includes this deliberation plan beside the
existing cognition/compute/knowledge/presentation projections.

## 13.30 — Memory action intelligence

`mary.memory.action_policy.MemoryActionPolicy` mines the useful part of
AgeMem/TaskMem-style memory operation selection while preserving Mary's existing
owners.

It can propose:

- ignore;
- working-memory only;
- episodic candidate;
- semantic candidate;
- temporal-update candidate;
- delegate to the relationship owner.

It **cannot write memory**. `MemoryManager.propose_action()` exposes the policy,
while the existing manager/consolidator/relationship system remains responsible
for actual persistence and promotion.

This complements 13.19 temporal projection: changed structured facts can be
identified as temporal-update candidates rather than flattening old and new
values into one timeless fact.

## 13.31 — Structural trajectory evidence

`mary.learning.trajectory.TrajectoryRecorder` adds the minimum evidence needed
for future process evaluation and offline learning:

- task class;
- reasoning strategy;
- pass/branch counts;
- verifier score;
- outcome/reward;
- provider attempt count;
- tool-call count;
- latency;
- token count;
- bounded failure kind/tags.

It deliberately stores **no prompt or response text**.

The existing performance-hardening bundle exposes this recorder so runtime code
has one place to submit structural trajectory evidence. Merely recording a
successful trajectory does not train, rewrite prompts, mutate identity, or
promote a model. Future DSPy/GEPA/Promptfoo/Phoenix/LoRA/RL experiments continue
through MaryBench and explicit promotion gates.

## 13.32 — Duplex/research runtime substrate

### Duplex interaction policy

`mary.realtime.duplex_policy.DuplexInteractionPolicy` provides a
transport-neutral policy for future Moshi/Pipecat/LiveKit-style conversation:

- bounded relational backchannels;
- creator barge-in remains allowed;
- evidence retrieval may overlap deliberate speech preparation;
- partial factual answers are not released before required evidence is ready.

The existing 13.18 TurnEndPolicy/RealtimeConversationLoop remain the actual
turn lifecycle. This layer adds only higher-level overlap/backchannel policy.

### Research runtime catalog

`mary.distributed.research_runtime_catalog` tracks optional candidates without
making them Core dependencies:

| Runtime family | Intended Mary role | Promotion status |
|---|---|---|
| Coconut | continuous latent-reasoning experiments | offline lab |
| recurrent reasoning | Huginn/TRM/MoDr-style recurrence/branching | offline lab |
| latent verifier | LTO/process-reward-style verification | evaluation lab |
| vLLM | future CUDA serving/speculative decoding | benchmark candidate |
| SGLang | future CUDA serving/cache/speculation | benchmark candidate |
| ExecuTorch | iPhone/iPad/edge inference | native-client candidate |
| MLC-LLM | Metal/mobile inference | native-client candidate |
| exo | heterogeneous distributed inference | experimental node fabric |
| Pipecat | realtime voice orchestration | optional transport |
| LiveKit Agents | WebRTC/realtime participant transport | optional transport |
| A2A gateway | delegation to independent workers | bounded gateway |
| AReaL | agent-RL experiments | offline lab |
| verl | RL/model optimization | offline lab |
| OpenTelemetry | structural GenAI trace export | optional exporter |

Readiness means only that a dependency/configuration is present. It is never
permission, routing preference, identity ownership or proof of quality.

## What was already present and therefore not duplicated

Current main already implemented much of the research direction before this
pass:

- 13.16 policy-safe adaptive model ranking;
- 13.17 provider-independent cognitive need/depth planning;
- 13.18 turn-end and barge-in primitives;
- 13.19 temporal/provenance memory projection;
- 13.20 external knowledge gateway;
- 13.21 cognitive workload -> home compute scheduling;
- 13.22 cognitive embodiment;
- 13.23 unified character runtime coordination;
- 13.24 local inference acceleration / MTP benchmarking;
- 13.25 local runtime intelligence;
- 13.26 ephemeral context activation;
- 13.27 bounded creative capability fabric;
- 13.28 rebuildable document evidence.

The new code composes with these owners instead of replacing them.

## Research-to-production promotion gate

Every experimental cognitive/runtime mechanism follows:

```text
paper/project idea
    -> bounded Mary-native interface
    -> optional lab/runtime
    -> deterministic tests
    -> MaryBench / representative task evaluation
    -> hardware/runtime benchmark where relevant
    -> privacy/cost/permission review
    -> creator approval
    -> production route
```

There is no direct path from “interesting paper” to production authority.

## Self-improvement boundary

Production Mary may collect bounded structural experience evidence. Training is
a separate offline activity:

```text
production structural trajectories
        |
        v
curated evaluation/training dataset
        |
        v
offline experiment (DSPy/LoRA/RL/etc.)
        |
        v
candidate artifact
        |
        v
MaryBench + deterministic gates + hardware benchmark
        |
        v
human promotion decision
```

No runtime may automatically rewrite Mary's identity, relationship history,
canonical memory, permissions, production prompts, source code, or active model
weights merely because an outcome was rewarded.

## Neuralese / latent-reasoning boundary

True latent reasoning requires direct access to model hidden states and is
therefore a separate experimental runtime, not a prompt trick. Mary may later
run Coconut/recurrent/latent-verifier experiments on open models through a
dedicated node/lab.

Production telemetry may retain:

- strategy name;
- number of passes/branches;
- verifier score;
- outcome/reward;
- latency/token/tool metrics.

It must not persist or expose:

- private chain-of-thought;
- raw hidden-state tensors;
- latent activations tied to private input;
- secret-bearing prompts/tool payloads.

## Verification

Focused deterministic tests added by this pass:

```powershell
python -m pytest tests/cognition/test_deliberation_governor_13_29.py -q
python -m pytest tests/memory/test_memory_action_policy_13_30.py -q
python -m pytest tests/learning/test_trajectory_telemetry_13_31.py -q
python -m pytest tests/realtime/test_duplex_policy_13_32.py -q
python -m pytest tests/distributed/test_research_runtime_catalog_13_32.py -q
python -m pytest tests/cognition/test_runtime_coordination_13_32.py -q
```

Read-only research status:

```powershell
python scripts/check_research_convergence.py
python scripts/check_research_convergence.py --json
```

After pulling this exact main on the target machines, the normal repository
gates still apply:

```powershell
python -m scripts.verify_repository_structure
python -m pytest -q
```

The M1 and Windows PC should test the **same commit**. Optional local runtimes
must be benchmarked on the actual host before any scheduler preference changes.
