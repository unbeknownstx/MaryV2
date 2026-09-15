# MaryV2 13.37 — Execution Reliability and Efficient Compute Fabric

Status: **ACTIVE FOUNDATION**

13.37 is a license-clean architecture convergence pass informed by public engineering patterns in local-AI runtimes and agent systems, including the operational lessons observed in Locally Uncensored. It adopts patterns, not source code. Mary remains governed by `MARY_ROOT.md`: one canonical Mary, replaceable cognition/compute capabilities, explicit permissions, and no provider/node authority over identity, memory, relationship, or developed self.

## Why this layer exists

13.11–13.36 already gave Mary the correct ownership model: heterogeneous nodes, benchmark-aware scheduling, task-aware model suitability, bounded MCP/sensor capabilities, computational-state tiers, and a Linux substrate. The next bottleneck is not another model provider. It is making imperfect models and finite hardware behave predictably.

13.37 therefore strengthens existing owners rather than creating a parallel agent runtime.

## Adopted engineering patterns

### 1. Correctness-weighted model evidence

Raw tokens/second is not intelligence. Local benchmark evidence can now carry bounded quality signals alongside latency and throughput:

- correctness rate;
- time to first token when available;
- output-token economy;
- reasoning-token share when a backend exposes it structurally;
- truncation/runaway finish classifications;
- useful throughput: measured throughput weighted by correctness.

Raw benchmark prompts and model responses are not operational telemetry. Standard benchmark cases are synthetic and the stored profile contains metrics/verdicts only.

`mary.llm.model_fabric` consumes accuracy when available. A fast but inaccurate worker can therefore be rejected for coding/deep reasoning even when its latency is excellent.

### 2. Content-free progress/loop protection

`mary.distributed.execution_reliability.ProgressGuard` recognizes structural stalls without retaining private reasoning or task content. It operates on capability names, bounded argument fingerprints, mutation epochs, and outcome classes.

It can:

- steer after repeated identical read operations;
- halt persistent repeated reads;
- steer/halt after consecutive no-progress failures;
- reset read-repeat evidence after a successful mutation;
- remain entirely non-authoritative.

This is designed for future wiring into bounded worker/agent loops. It does not itself execute or cancel anything.

### 3. Safe retry policy

Retries are now a first-class policy rather than a generic reflex:

- transient + non-mutating work may retry under a bounded attempt budget;
- mutation is never blindly replayed because the effect may have landed before a transport failure;
- cancellation is user/runtime intent and is never classified as transient;
- historical transient classes (`timeout`, `busy`, `rate_limited`, `transport_error`, `temporarily_unavailable`) remain supported.

`CapabilityInvocationLedger` uses this policy while remaining process-local orchestration state.

### 4. Side-effect/resource serialization vocabulary

`derive_side_effect_key()` provides a deterministic resource namespace for work that must not race:

- one local inference runtime can be serialized per capability when needed;
- MCP calls are conservatively keyed by exact server/tool;
- image/video/creator workloads share accelerator keys;
- pure reads/sensors remain keyless unless a caller adds a stricter contract.

The key is scheduling evidence only. It never grants permission.

### 5. Advisory resource handoff planning

`mary.distributed.resource_broker` models the useful part of VRAM handoff without importing another runtime manager.

Given sanitized resource facts and a workload footprint it can plan:

- run alongside the current resident model;
- serialize on an accelerator;
- preserve/unload/restore warm model state when the workload only fits after release;
- refuse an impossible fit;
- protect a realtime-critical node from background eviction;
- decline to evict in `auto` mode when measurements are unknown.

The plan is intentionally **planning-only**. A future node-local runtime adapter may implement save/unload/restore for Ollama, llama.cpp, MLX, ComfyUI or another engine, but this module never owns those processes and never treats a KV/cache artifact as Mary memory.

### 6. Quality-aware node routing

`NodeRegistry.route_preview()` now transports the richer benchmark projection so `model_fabric` can distinguish availability from suitability using the same evidence. `NodeRegistry.choose()` uses quality as a tie-breaker among already-routable candidates without making old/unbenchmarked nodes disappear.

The authority chain stays:

```
discovery -> benchmark evidence -> ranking -> typed task -> local permission -> execution
```

There is intentionally no shortcut from benchmark success to permission.

## Existing Mary systems that already satisfy mined patterns

The audit also found several LU-style lessons Mary already implements correctly, so 13.37 does **not** duplicate them:

| Pattern | Existing Mary owner | Decision |
|---|---|---|
| One identity above replaceable models | `MaryApplication` / Core | keep |
| Typed device tasks, no generic shell capability | `DeviceTaskBroker` | keep |
| Device-local deny-by-default permissions | `DeviceExecutionPermissions` | keep |
| Exact MCP server/tool allowlists | `MCPFabric` + permissions | keep |
| MCP discovery != authorization | distributed permission boundary | keep |
| Bounded sanitized task args/results | `mary.distributed.tasks` | keep |
| Model role selected by node, not arbitrary Core model ID | device node executors | keep |
| Context cap on constrained local nodes | device Ollama executor | keep |
| Heartbeat/stale-node expiry | `NodeRegistry` | keep |
| Rebuildable benchmark evidence | compute fabric / computational state contract | keep |
| Frontier providers benchmark-before-promotion | model fabric 13.35 | keep |
| Paid expert routes explicit only | LLM router/model fabric | keep |
| Warm model/cache state non-authoritative | computational state 13.34 | keep |

## Patterns deliberately not copied directly

### Generic desktop agent shell

Mary's capability fabric deliberately excludes arbitrary shell execution from remote/node task authority. A software-engineering worker remains a separately sandboxed worker boundary. This is safer than turning Core into an IDE agent.

### Third-party identity/persona stores

Provider personas, agent personas and model-specific memory are not imported into Mary identity. Character evidence continues through the Character Sourcebook and canonical identity/developed-self owners.

### Raw chain-of-thought telemetry

Reasoning-token counts may be operational evidence when a provider exposes them, but reasoning text is neither a benchmark artifact nor Mary memory.

### Automatic model promotion

A benchmark can make a candidate *eligible/preferred for a lane*. It cannot authorize spend, enable a device permission, rewrite routing policy, change prompts, or self-promote experimental training output.

## Next implementation hooks

The following are now safe extension points rather than architectural gaps:

1. **Node-local resource adapters** — implement optional save/unload/restore for specific runtimes behind `ResourceHandoffPlan`.
2. **Execution scheduler** — consume side-effect keys when a run emits independent capability requests; reads may parallelize while conflicting mutations/resources serialize.
3. **Broader benchmark suites** — coding, tool-call JSON/schema accuracy, retrieval, summarization, memory reconciliation, vision and character-delivery tests, storing only synthetic verdicts/metrics.
4. **Runtime capability probes** — prefer measured context/tool/vision/runtime facts over model-name guesses and fingerprint every benchmark to the exact runtime/model configuration.
5. **Context efficiency** — age/compact rebuildable tool evidence while canonical history remains untouched; preserve exact creator instructions when summarizing old task context.
6. **Memory retrieval calibration** — require absolute relevance evidence before relative ranking can inject memory; retain scope/provenance/supersession authority in canonical memory rather than the retrieval index.
7. **Creator/accelerator workers** — ComfyUI or future media workers may consume the same resource plan without becoming Core dependencies.

## Acceptance properties

13.37 is correct only if all of the following remain true:

- a model/node can become faster or score higher without gaining permission;
- deleting every benchmark/resource/loop-guard record cannot erase Mary continuity;
- no operational record stores raw prompts, responses or chain-of-thought;
- mutating failures are not automatically retried;
- cancellation never causes an automatic replay;
- unbenchmarked legacy nodes remain usable but are not falsely called proven;
- unknown VRAM/resource facts do not trigger speculative eviction in automatic mode;
- resource planning never starts/stops a model by itself;
- Core can cold-start with all optional local runtimes absent;
- one canonical Mary remains above every worker/model/runtime.
