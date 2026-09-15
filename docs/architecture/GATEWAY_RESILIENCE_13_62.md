# MaryV2 13.62 — bounded gateway resilience

Mary independently adapts useful multi-provider gateway patterns while preserving Mary Core as the only identity/state authority.

## Added

- `ProviderQuotaBook`: bounded process-local RPM/RPD/token accounting with configurable reserve headroom.
- `FailoverBudget`: per-request circuit breaker preventing a sick provider pool from causing a long retry cascade.
- `ProviderHealthBook`: aggregate content-free `healthy/rate_limited/invalid/unreachable/unknown` observations with TTL and fail-open unknown state.

These are routing primitives, not Mary memory. They retain no prompt, response, API key, creator data, relationship state, or canonical identity state.

## Why

Provider quotas are often shared across models, so model-local counters alone can overspend an account-wide pool. A reserve margin also lets Mary move away from a nearly exhausted free lane before the provider starts returning 429s. When a provider fleet is broadly unhealthy, a bounded failover budget prevents realtime conversation from walking an arbitrarily long chain.

## Authority and safety

- Existing configured provider order remains the creator policy.
- Unknown quota/health evidence is fail-open; Mary does not invent limits.
- Known invalid/rate-limited evidence may suppress an attempt but cannot grant permissions or enable a provider.
- Paid/expert authorization is unchanged.
- Private/local routing is unchanged.
- No automatic key import, catalog trust, secret storage, or remote authority is added.
- No response caching is enabled for relational/private conversation.

## Next wiring rule

These primitives should be integrated into `LLMRouter` only at the existing candidate-filter/attempt boundary, after privacy/cost/capability eligibility and before provider interaction. Provider order should remain stable when no evidence exists. Successful/failed attempts may update only content-free operational evidence.
