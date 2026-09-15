# Model Residency Planning 13.45

MaryV2 13.45 adds an advisory warm-model residency planner for finite GPU/accelerator memory.

The goal is simple: keep useful low-latency models resident when resources permit, but identify lower-priority models that can yield when a measured incoming workload needs the memory. This complements 13.37 resource handoff and 13.40 live VRAM observation.

## Planner inputs

`mary.distributed.model_residency` consumes:

- a measured `ResourceSnapshot`;
- the models currently resident on that node;
- optional incoming `WorkloadFootprint` requirements;
- a small free-VRAM reserve target.

Each resident model can carry:

- exact model ID;
- estimated resident VRAM;
- role/lane;
- time since last use;
- pinned state;
- realtime/interactive importance;
- approximate reload cost.

## Conservative behavior

- Unknown free VRAM means **no speculative eviction**.
- Pinned models are never selected for release by this planner.
- Conversation/fast/STT/TTS/VAD or explicitly realtime models are protected.
- Stale lower-priority models become release candidates first under measured pressure.
- Recently used models with expensive reload cost can remain warm when pressure is not critical.
- If the incoming workload cannot fit even after safe candidates are released, the planner says so rather than pretending the node can run it.

## Authority boundary

A `ResidencyPlan` is `planning_only`. It does not call Ollama, kill a process, unload a model, free VRAM, or launch an incoming workload.

Any future release/reload operation must be implemented as an explicit node-owned capability and remain subject to Mary’s existing device permissions, resource serialization, cancellation, and creator/runtime policy.

## Why this matters

Mary’s hardware strategy is heterogeneous and opportunistic. A 4 GB GPU, M1 unified-memory node, future 12–16 GB GPU, or 24 GB compute node should not all be treated the same. Nor should a small conversational model be evicted every time a background job appears if another node is available.

13.45 gives the scheduler a deterministic answer to “what is worth keeping warm?” without turning resource management into uncontrolled process automation.
