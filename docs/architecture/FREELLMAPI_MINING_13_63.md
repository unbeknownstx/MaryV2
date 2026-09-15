# FreeLLMAPI mining — MaryV2 13.63

This tranche independently adapts additional useful gateway engineering while preserving Mary Core as the sole identity/state authority.

## Added

- `adaptive_provider_routing.py`: advisory reliability/latency/quota/capability scoring, explicit task-type weighting, route hysteresis, and opt-in exploration of unmeasured eligible providers.
- `endpoint_policy.py`: custom endpoint URL policy that always rejects cloud-metadata/link-local/unsafe IP destinations, makes loopback/private LAN explicit, and exposes a connection-time resolved-address check for DNS-rebinding protection.
- `provider_analytics.py`: bounded content-free success, p50/p95 latency, and TTFT diagnostics.

## Boundaries

Eligibility happens before adaptive scoring. Privacy, creator authorization, local-only policy, paid-provider authorization, model capability, and provider availability cannot be overridden by a better score. Task type is explicit metadata; Mary does not inspect private prompt text merely to optimize provider routing. Exploration is opt-in and only among already-eligible providers. Analytics never retain prompts, responses, credentials, relationship data, memory, or creator content.

## Mined but deliberately not copied literally

FreeLLMAPI is a gateway and can own its own sticky sessions, catalogs, keys, and compression pipeline. Mary already has canonical continuity, provider boundaries, context lifecycle, and identity authority. We reuse the operational ideas rather than allowing a gateway to become a second brain or memory authority.

## Still useful for later integration

- Wire 13.60–13.63 operational evidence into the existing router only after its current privacy/cost/capability eligibility checks.
- Signed remote catalog ingestion should require signature verification, freshness/provenance, schema bounds, and advisory-only authority before Mary consumes it.
- Gateway `/livez`/`/readyz` style readiness can be projected into Mary's existing diagnostics without becoming a startup dependency.
- Independent embeddings routing remains a good next subsystem because embedding availability should not depend on the current chat model.
