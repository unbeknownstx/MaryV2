# Discovery-to-Measurement Pipeline 13.49

MaryV2 13.49 connects bounded local-engine discovery to the model-evidence pipeline without enabling discovered engines automatically.

## State machine

The intended path is now explicit:

`discover -> qualify exact runtime identity -> probe structural capabilities -> benchmark correctness/latency -> measure resource fit -> explicitly adopt/routable`

A reachable endpoint is only a candidate. A model appearing in `/models` or Ollama `/api/tags` does not prove quality, trust, privacy suitability, tool support, or execution permission.

## Qualified candidates

`candidates_from_discovery()` converts each discovered engine/model pair into a 13.39-style qualified runtime identity bound to the node that discovered it. Candidates carry:

- node ID;
- engine ID;
- exact model ID;
- protocol;
- loopback base URL;
- engine-identity strength;
- qualified model ID;
- model fingerprint;
- explicit `measurement_required` state.

No candidate is auto-promoted.

## Required evidence

`measurement_plan()` requires:

- 13.44-style structural capability probes (`structured_json`, tools, vision, embeddings);
- correctness/latency benchmarks for conversation and task-generation lanes;
- resource-fit evidence from the live resource layer;
- preservation of ambiguous engine identity when a shared conventional port is all that is known.

## Authority boundary

The catalog reports `execution_authorized: false` and `auto_promoted: 0`. Explicit runtime/provider adoption remains separate from discovery. Normal Mary privacy/cost policy, node permissions, provider policy, benchmark evidence, and creator/runtime authorization still decide whether a candidate can actually receive work.

This makes heterogeneous local compute easier to plug in without weakening the one-Mary / replaceable-worker architecture.
