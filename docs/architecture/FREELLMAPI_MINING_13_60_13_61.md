# FreeLLMAPI mining — MaryV2 13.60–13.61

Mary independently adapts useful gateway engineering while preserving one canonical Mary Core. FreeLLMAPI or any other meta-gateway is an optional replaceable inference lane, never identity/memory/state authority.

## Incorporated

- 13.60 process-local provider pressure/quota/reliability evidence.
- Optional loopback OpenAI-compatible FreeLLMAPI lane.
- 13.61 capped output reservation and per-request token-budget helper.
- 13.61 disposable prompt-projection fidelity gate protecting numbers, JSON keys, diff hunks, and explicit creator constraints.
- 13.61 bounded model session affinity storing only opaque session/model IDs.

These complement Mary's existing provider cooldowns, typed GenerationRequest privacy/cost/capability constraints, context lifecycle, model capability evidence, execution budgets, node scheduling, and local-engine discovery.

## Useful patterns retained for future wiring

- task-type-aware scoring rather than one universal provider ranking;
- quota headroom/hysteresis so a nearly exhausted provider can be preserved before hard 429;
- provider liveness/readiness aggregate state;
- failover attempt budgets and cooldown ceilings;
- model capability filtering before attempts (vision/tools/structured output/context);
- error redaction at provider boundaries;
- local/custom endpoint SSRF protections;
- embeddings as a separate replaceable capability lane;
- content-free p50/p95/TTFT/provider analytics.

## Deliberately not copied

- no provider gateway may own Mary's conversation history or identity;
- no remote/self-updating catalog grants permissions or becomes routing authority without Mary-side validation/provenance;
- no response cache for private/relational conversation by default;
- no automatic provider-key import into Core;
- no localhost authentication bypass;
- no twenty-attempt fallback loop for realtime Mary conversation;
- no inferred capability is trusted over measured evidence;
- no prompt compression may mutate canonical transcript/state.

## Fidelity rule

Compression/decay operates only on a disposable prompt projection. If the fidelity gate cannot prove preservation of high-risk literals/constraints, Mary uses the uncompressed projection instead. Canonical transcript remains untouched.

## Affinity rule

Sticky model selection is a latency/continuity hint only. Mary Core already owns continuity. Affinity may expire or disappear without changing Mary's identity, memory, relationship, or canonical state.
