# MaryV2 13.16 — Model Intelligence / Compute Scheduler

## Purpose

Mary is one canonical identity and runtime authority. Language models are interchangeable compute workers, not Mary's identity. 13.16 adds an adaptive model-intelligence scheduler that can learn which already-authorized provider/model routes perform best without weakening Mary's privacy, spend, capability, or fallback boundaries.

## Hard policy before scoring

The scheduler never decides which providers are legally or operationally allowed for a request. The existing LLM router first applies:

1. operation compatibility,
2. privacy mode (`cloud_ok`, `redact_first`, `local_only`),
3. cost authorization (`zero_local`, `free_cloud`, `paid_low`, configured),
4. structured-output/deadline capability,
5. explicit route/provider overrides,
6. fallback eligibility,
7. local/private route rules.

Only the resulting eligible list is passed to the model scheduler. The scheduler can reorder that list but cannot add a provider that the router excluded. Paid providers therefore cannot become authorized through a good benchmark score, and local-only requests cannot escape to cloud inference.

## Cold start and deterministic fallback

Adaptive mode is intentionally conservative. Until a provider has enough measured evidence, Mary's existing deterministic provider order remains unchanged. The default minimum is three observations. `ordered` mode disables adaptive reordering entirely.

The incoming route order remains a strong prior even after learning. This prevents a small or noisy sample from erasing Mary's local/free-first policy.

## Evidence Mary can learn from

The scheduler stores only bounded structural measurements:

- attempts, successes, hard failures, and soft/rate-limit failures;
- consecutive failures;
- latency EWMA when supplied;
- bounded quality EWMA when supplied by an evaluation/benchmark layer;
- prompt/completion/reasoning/cached token counters;
- token-efficiency EWMA;
- cache-ratio EWMA.

It never stores prompts, responses, message bodies, API keys, provider exception prose, or raw provider payloads.

## Scoring

For providers with sufficient evidence, ranking combines:

- the incoming policy-order prior;
- reliability;
- optional quality evidence;
- optional latency evidence;
- structural token efficiency;
- a bounded penalty for repeated consecutive failures.

This is not a universal model leaderboard. The score is Mary-specific operational evidence collected from the routes she actually uses.

## Resource governance integration

`ResourceGovernor.provider_order()` now performs:

`router-eligible providers -> adaptive ranking -> hard provider-attempt ceiling`

The existing provider-attempt maximum remains authoritative after ranking.

`ResourceGovernor.record_attempt()` feeds provider outcomes to the scheduler. `record_usage()` feeds token telemetry to the last successful provider. `record_model_measurement()` is the bounded bridge for future benchmark/evaluation systems to add latency, quality, and usage evidence without passing generated content into scheduler state.

## Modes

Default mode: `adaptive`.

Optional process configuration:

- `MARY_LLM_SCHEDULER=adaptive|ordered`
- `MARY_LLM_SCHEDULER_MIN_SAMPLES=<1..50>`
- `MARY_LLM_SCHEDULER_EWMA_ALPHA=<0.05..1.0>`

These are optional tuning controls; Mary does not require new API keys or secrets for the scheduler itself.

## Next evolution

13.16 establishes the policy-safe learning core. Later extensions can feed it richer content-free measurements from Mary's benchmark harness and capability nodes, including task-class-specific quality, device/model residency, measured first-token latency, throughput, context pressure, cache efficiency, and current hardware availability.

Those extensions must preserve the same rule: **hard authorization first, adaptive scoring second.**
