# MaryV2 13.64 — FreeLLMAPI-derived integration boundary

Mary independently adapts useful gateway engineering while preserving one canonical Mary Core. FreeLLMAPI, provider catalogs, cloud models, local engines, and specialist workers remain replaceable inference infrastructure.

## 13.64 additions

- `catalog_trust.py`: pinned-key, signed catalog envelope policy with freshness, expiry, sequence rollback/replay protection, and payload digest. Verification is dependency-injected; catalog data is routing metadata only and cannot grant permissions or mutate Mary state.
- `readiness.py`: TTL-bounded readiness aggregation. Unknown evidence stays unknown rather than becoming an invented outage.
- `embedding_router.py`: independent embedding-family routing. Failover may cross providers only when family, dimensions, and embedding-space identity are identical. This matches Mary's existing vector-index identity protections and prevents silent vector-space corruption.
- `provider_identity.py`: detects provider/model substitution. Explicit requests reject substitutions by default unless the caller deliberately permits them.
- `quota_hysteresis.py`: separate enter/leave thresholds prevent route flapping near scarce-quota boundaries.
- `transport_normalization.py`: canonical OpenAI-style image parts plus capability prefiltering. Normalization does not itself authorize network fetching; endpoint/network policy remains a separate security boundary.
- `ResourceGovernor`: 13.60–13.63 provider pressure, health, quota accounting and quota hysteresis are now on the real generation path **after** `LLMRouter.route_order()` applies privacy/cost/operation/structured-output/fallback eligibility. Governance can remove, demote, or reorder only members of that already-authorized list; it cannot introduce a provider.

## Ordering invariant

`GenerationRequest` constraints -> provider route eligibility -> ResourceGovernor operational filtering/scoring -> bounded attempts -> provider execution.

This ordering is intentional. Operational optimization never outranks authorization.

## Embeddings

Chat failover and embedding failover are different problems. Chat may switch models when policy permits. Embeddings must remain in one compatible vector space for a given index. Mary's existing `EmbeddingIdentity`/vector-index fingerprints remain authoritative for stored vectors; the new embedding router is a provider failover seam, not a replacement for those identities.

## Catalog trust

A signed catalog can describe models, quotas, quirks, and capabilities. It cannot enable a provider, install a model, add a secret, widen permissions, change privacy policy, or alter Mary identity/memory. A stale, expired, replayed, unpinned, or badly signed catalog is rejected and the last creator/configuration-approved state remains authoritative.

## Provider substitution

Gateways may serve a different upstream model/provider than requested. Mary records this as operational route identity and rejects unexpected substitution where exact identity matters (especially embeddings, explicit model requests, benchmarks, and capability qualification). An `unreported` served identity is not treated as proof of a match.

## Image transport

Vision requests use a canonical content-part representation and must be capability-prefiltered before execution. If no vision-capable route is known, the request should fail clearly rather than dropping the image. Remote image URL fetching, if enabled by a provider surface, remains subject to endpoint/SSRF policy; normalization is not network authorization.

## What remains non-authoritative

Provider scores, quotas, health, readiness, catalogs, latency, TTFT, gateway route headers, and embedding-provider availability are operational evidence. None are Mary memory, identity, relationship state, creator authority, or permission state.
