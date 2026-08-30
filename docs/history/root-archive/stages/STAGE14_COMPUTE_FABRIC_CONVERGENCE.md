# MaryV2 13.2 — Stage 14 Compute-Fabric Convergence

Stage 14 closes a visibility and routing-truth gap without creating a second scheduler, identity owner, or model stack.

## What changed

- `LLMRouter.routing_status()` exposes one display-safe view of general, conversation, private, and expert routes.
- Every generation records the requested route/purpose, ordered candidate engines, selected provider/model, outcome, attempts, and timings.
- `MaryCoreService.compute_fabric_status()` combines model-route truth with the existing node registry and bounded device-task broker.
- Core state and desktop dashboard now expose the same `compute_fabric` contract.
- The `llm.ollama` capability route is previewed explicitly so Mary can truthfully report whether a replaceable Ollama node is presently routable.
- A routable capability remains **not authorized** until the existing device-task permission path authorizes execution.

## Why this matters

Mary already had cloud providers, local Ollama, a remote `DeviceOllamaProvider`, a node registry, and a capability task broker. Before this pass those systems worked, but runtime truth was scattered. Stage 14 makes them observable as one compute fabric while preserving their separate responsibilities.

This is the basis for later intelligent workload placement across several bounded local models and cloud specialists: routing decisions can now be inspected and tested instead of inferred from logs.

## Invariants preserved

1. Mary Core remains the only identity/state authority.
2. Models are engines, not Mary.
3. Capability nodes are replaceable executors, not state owners.
4. Capability availability is not execution authorization.
5. No shell or arbitrary command execution is introduced.
6. No new paid provider is required.
7. No `.env` or checked-in `data/` content is part of the drop-in.
