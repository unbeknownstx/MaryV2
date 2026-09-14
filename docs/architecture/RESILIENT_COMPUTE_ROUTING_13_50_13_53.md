# MaryV2 13.50–13.55 — Resilient Compute Routing

## Purpose

MaryV2 uses replaceable capability nodes without moving identity, memory, relationship state, permissions, or canonical truth out of Mary Core. The 13.50–13.55 extension makes that compute fabric more resilient, situationally aware, fit-aware, and explainable while preserving the same authority boundary.

The routing stack now reasons from five bounded classes of operational evidence:

1. claim health and replay safety;
2. measured execution success/latency;
3. currently claimed realtime/background work;
4. fresh RAM/accelerator pressure reported by capability nodes;
5. explicit device-local workload-fit measurements/configuration.

None of these signals grants execution permission.

## 13.50 — Attempt isolation and claim rollover

`mary.distributed.tasks.DeviceTaskBroker` applies a bounded claim lease to device work.

When a claimed task exceeds the lease:

- replay-safe work is rolled over to a **new canonical task ID**;
- the old task becomes terminal `expired` and records `replacement_task_id`;
- `wait_for_terminal(original_id)` follows the replacement chain;
- a late completion for the old task can only reach the already-terminal old task and cannot overwrite the retry;
- retries stop at `max_claim_attempts`.

Replay-safe capabilities are deliberately narrow. Local inference/search/sensor reads may be retried under the broker policy; MCP/mutating work is not blindly replayed.

This avoids protocol token churn and stale-attempt races while keeping existing node executors compatible.

## 13.51 — Measured reliability routing

The real `DeviceTaskBroker` owns a process-local `BenchmarkBook` and `HomeComputeScheduler`.

Cold start remains conservative: when there is no runtime evidence, existing `NodeRegistry.choose()` behavior and static benchmark metadata remain authoritative for selection among already-eligible nodes.

After claimed work completes, the broker records content-free evidence:

- node ID;
- capability;
- normalized operation;
- success/failure;
- claimed-to-completion latency.

The benchmark book never retains task intent, prompt text, arguments, result content, lease data, credentials, or Mary state.

Local permission rejection is not counted as hardware/model unreliability because it means "not authorized on this device", not "this worker failed to execute".

## 13.52 — Broker-derived live load

Before choosing a node, the broker derives current pressure from its own claimed tasks.

Realtime operations include conversation, quick-answer, STT, and vision lanes. Other claimed work counts as background load.

This lets the scheduler protect a stream/conversation-critical node from avoidable background work. Once claimed pressure clears, static/runtime benchmark preference can return naturally.

No new node telemetry is required for this layer and no remote party can fabricate task-count pressure: it is derived from Core-owned broker state.

## 13.53 — Fresh bounded resource pressure

### Node observation

`mary.distributed.resource_probe` provides bounded best-effort RAM/GPU observation using fixed probes with short timeouts. Missing vendor utilities are normal and never become a Core startup dependency.

`mary.distributed.resource_telemetry` projects observations into exactly six transport fields:

- `ram_total_gib`
- `ram_free_gib`
- `vram_total_gib`
- `vram_free_gib`
- `apple_unified_memory`
- `source`

Unknown fields are rejected. Numeric values are bounded and free memory may not exceed total memory.

Paths, process lists, environment variables, model names, prompts, outputs, credentials, arbitrary metadata, and hardware-control commands are not part of this channel.

### Transport

`mary.runtime.resource_reporting_gateway.ResourceReportingGateway` is used only by capability-node launch paths.

The wrapper:

- delegates all authority and transport behavior to the existing gateway;
- warms and refreshes hardware observations on a daemon thread;
- never waits for hardware probes on task completion;
- attaches `_resource` only to successful completions when a fresh cached report exists;
- does not probe because work was rejected or failed;
- preserves the existing eight-field completion result budget by skipping resource injection for a full business result;
- fails soft when a probe is unavailable.

The canonical headless launcher `scripts.run_home_node` and optional Desktop compatibility capability node use this wrapper. Ordinary mobile, creator-surface, diagnostic, and turn clients do not.

### Core ingestion

`DeviceTaskBroker.complete()` removes `_resource` before capability result sanitization/storage. Valid telemetry is converted into process-local `NodeLoad` resource pressure/capacity; malformed telemetry increments a rejection counter without changing the task's success/failure status.

Resource reports are process-local and expire quickly (90 seconds by default). Stale reports disappear rather than being treated as durable knowledge.

Apple Silicon is modeled as unified memory; the system does not pretend unified RAM is dedicated VRAM.

## 13.54 — Explicit fit-aware routing

The pre-existing 13.37 `plan_resource_handoff()` planner is now part of live scheduling, but only when the node supplies an explicit resource requirement.

Mary does **not** infer memory requirements from model names, parameter counts, quantization labels, GPU brands, or marketing specifications.

Supported fixed metadata hints are:

- `resource_accelerator_gib_general`
- `resource_accelerator_gib_conversation`
- `resource_accelerator_gib_fast`
- `resource_accelerator_gib_utility`

Capability-node operators may supply the corresponding device-local environment values:

- `MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB`
- `MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_GENERAL`
- `MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION`
- `MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_FAST`
- `MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_UTILITY`
- `MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB`
- `MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB_GENERAL`
- `MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB_CONVERSATION`
- `MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB_FAST`
- `MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB_UTILITY`

The common value fills missing roles; a role-specific value overrides it. These values should come from actual device-local measurement/configuration, not guesses.

Fit behavior is deliberately bounded:

- `fits`: small scheduling confidence bonus;
- `handoff` / `prefer_other_node`: scheduling penalty only;
- `unknown`: existing routing behavior is preserved;
- `infeasible`: that candidate is removed;
- if every otherwise-eligible candidate has explicit fresh evidence proving no fit, enqueue fails cleanly instead of knowingly scheduling an out-of-memory workload.

The fit planner never unloads/evicts a model automatically and never makes an untrusted, offline, unavailable, or unpermitted node eligible.

Apple Silicon uses explicitly reported unified-memory capacity as accelerator capacity; discrete GPU nodes use measured VRAM.

## 13.55 — Explainable adaptive routing

`BenchmarkBook` now retains one bounded **last adaptive routing decision** as disposable operational diagnostics. It is surfaced through the broker's existing `compute_status()` benchmark projection, so no new network endpoint or permission surface is required.

The diagnostic may contain:

- capability and normalized operation;
- selected node ID or no-fit outcome;
- up to eight candidate node IDs;
- bounded scores/reasons/load pressure;
- content-free benchmark summaries;
- a timestamp and authority marker.

It never contains task intent, messages, prompt text, arguments, model/tool result content, raw resource envelopes, credentials, or arbitrary candidate metadata.

Cold-start `NodeRegistry` fallback is not mislabeled as an adaptive decision: the decision remains empty until the adaptive scheduler actually participates.

This makes PC/Mac testing auditable: a creator can see whether a route was influenced by measured reliability, current load, resource pressure, or explicit fit evidence without exposing the private work itself.

## Selection order and authority

A useful conceptual order is:

```text
NodeRegistry eligibility
    ↓
trust + liveness + advertised capability
    ↓
existing static benchmark preference
    ↓
measured success/latency evidence (when available)
    ↓
Core-derived claimed-work pressure
    ↓
fresh RAM / accelerator pressure
    ↓
explicit measured/configured workload fit (when available)
    ↓
advisory best-worker selection + content-free explanation
    ↓
DeviceTaskBroker dispatch
    ↓
node-local permission gate
```

Resource capacity, benchmark speed, fit evidence, or scheduler score can **never** make an otherwise ineligible node trusted, live, capable, or authorized.

## Privacy and retention

All 13.50–13.55 scheduling evidence is operational and disposable. It is not:

- Mary memory;
- relationship state;
- personality/growth state;
- authored character truth;
- durable autonomy state;
- a permission store;
- a provider prompt/result log.

A process restart may discard the evidence safely and rebuild it from future executions.

## Hardware philosophy

This extension supports Mary's "use what you have" architecture. A Windows PC, Mac, future CUDA GPU, older server GPU, or other bounded worker can remain replaceable. Mary Core does not need to become the largest inference process; it coordinates workers using eligibility, observed quality, current contention, fresh resource pressure, and explicit task-fit evidence while protecting one canonical identity.

## Verification targets

The deterministic suite covers:

- stale-attempt isolation and replacement lineage;
- retry exhaustion / unsafe replay suppression;
- cold-start compatibility;
- runtime and static benchmark evidence influencing routing correctly;
- permission rejection excluded from reliability scoring;
- realtime/background load balancing;
- strict resource telemetry validation;
- resource-pressure routing and expiry;
- resource result stripping / no content retention;
- asynchronous node-side resource sampling;
- probe failure remaining fail-soft;
- legal full result payloads remaining valid;
- explicit fit routing and stale-fit fallback;
- all-measured-no-fit fail-closed behavior;
- Apple unified-memory fit;
- unavailable nodes not resurrected by capacity;
- fixed fit-hint projection at node registration;
- bounded/content-free adaptive route diagnostics;
- cold registry fallback not misattributed to the adaptive scheduler.

Platform, convergence, native iPhone, and web gates remain independent guards that this compute work does not accidentally move Mary authority into a client or node.
