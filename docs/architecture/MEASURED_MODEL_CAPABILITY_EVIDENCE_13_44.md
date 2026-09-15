# Measured Model Capability Evidence 13.44

MaryV2 13.44 formalizes a content-free evidence contract for proving what an **exact model runtime** can actually do.

Model names and server advertisements are useful hints, but 13.39 already established the truth hierarchy `measured > advertised > known > heuristic > unknown`. 13.44 supplies a reusable measured-evidence object that local adapters can populate without persisting probe prompts, model replies, or hidden reasoning.

## Evidence shape

`mary.distributed.model_capability_evidence` provides:

- `CapabilityProbeResult` — capability name, supported/unsupported/unknown, latency and normalized error class;
- `ModelCapabilityEvidence` — exact qualified model ID + exact model-instance fingerprint + bounded probe outcomes;
- `run_boolean_probe()` — normalizes one adapter-owned bounded probe;
- `build_capability_evidence()` — builds one evidence bundle for an exact runtime instance.

The evidence bundle can project into capability metadata using `metadata_overlay()`.

## Supported structural facts

The overlay currently understands measured evidence for:

- native tool calling;
- vision input;
- thinking/reasoning mode;
- embeddings;
- structured JSON;
- loaded context allocation;
- trained/advertised maximum context when independently verified.

Existing 13.39 model-instance projection already consumes measured tool, vision, thinking, embeddings and loaded/trained context facts. A measured `False` is intentionally stronger than an advertised or heuristic `True`.

## Privacy boundary

Capability probes must return structural success/failure only. The evidence record does not retain:

- prompt text;
- model response text;
- chain-of-thought/reasoning;
- private creator data;
- provider exception messages;
- tool outputs.

Errors are reduced to compact classes such as `timeout`, `transport`, `permission`, or `probe_failed`.

## Execution boundary

13.44 does not itself contact a provider. Engine adapters own the actual bounded test operation and pass a callable into the evidence builder. This keeps protocol quirks in the correct adapter and prevents a second provider stack from growing inside the capability registry.

A successful capability probe does not grant permission to use that capability. ToolManager, device permissions, MCP allowlists, routing/privacy policy, resource policy and creator approval remain authoritative.

## Intended progression

A discovered 13.42 engine is only a candidate. After explicit adoption, 13.39 assigns the exact runtime/model identity. 13.44 records measured structural capabilities for that exact fingerprint. 13.37/13.43 benchmarks then establish whether the runtime is **good enough**, not merely capable enough, for a particular workload lane.
