# MaryV2 13.64 — Unified provider and model execution fabric

MaryV2 13.60–13.64 is not a second routing stack. It is the operational-evidence layer of the existing provider catalog, LLM router, ResourceGovernor, and Model Execution Fabric. FreeLLMAPI was an engineering research source; it is not Mary authority, a required runtime dependency, or a second brain.

## Canonical composition

The provider/model path is one pipeline:

`GenerationRequest constraints -> LLMRouter eligibility -> ResourceGovernor operational evidence -> bounded provider attempts -> normalized response`

The owners are:

- `mary.llm.provider_catalog`: secret-free creator/configuration-approved provider metadata and direct frontier/open-model presets.
- `mary.llm.router`: hard privacy, cost, operation, structured-output, fallback and explicit-route eligibility.
- `mary.governance.resource.ResourceGovernor`: process-local health, quota, pressure, hysteresis and adaptive scheduling over **only** the already-eligible providers.
- `mary.llm.model_fabric`: task-lane suitability, local/node feasibility, provider/model portfolio projection and benchmark-before-promotion policy.
- `mary.llm.model_instances` / provider identity helpers: qualified route/model identity so operational evidence cannot silently collapse distinct endpoints or served models.

No one of these layers may introduce a provider that the preceding authorization layer excluded.

## 13.60–13.64 capabilities now owned by that fabric

- provider pressure, cooldown and quota headroom are ephemeral routing evidence;
- provider health/readiness is TTL-bounded and unknown stays unknown;
- quota hysteresis prevents route flapping near scarcity thresholds;
- adaptive provider scoring is subordinate to hard router eligibility and deterministic cold-start order;
- bounded failover budgets stop unhealthy chains;
- provider/model substitution is detected and exact-identity work rejects unexpected substitution by default;
- signed external catalogs are routing metadata only, with pinning, freshness, expiry and replay/rollback protection;
- OpenAI-compatible gateway transport remains optional and replaceable rather than a Core startup dependency;
- endpoint policy keeps remote/private/link-local access explicit and prevents a catalog from granting network authority;
- request budgeting, session affinity, context-fidelity checks and content-free analytics remain support systems around the same execution path;
- vision transport is capability-prefiltered instead of silently dropping image input;
- embeddings have a separate compatibility route: failover may cross providers only when family, dimensions and embedding-space identity are identical.

## Provider catalog relationship

The 13.15 frontier presets and the 13.60–13.64 gateway work describe the same replaceable inference portfolio. A catalog entry can describe a provider/model/endpoint and its advertised capabilities, but it cannot enable credentials, widen permissions, change privacy/cost policy, auto-promote a model, or alter Mary state. Live readiness and benchmark evidence may refine whether an approved route is suitable; they do not rewrite the catalog's authority.

FreeLLMAPI itself is best treated as an optional OpenAI-compatible gateway endpoint beneath Mary's fabric. Direct Groq/Gemini/OpenRouter/frontier providers, local Ollama/llama.cpp engines, capability nodes, and a FreeLLMAPI gateway can coexist because Mary owns routing policy above them.

## Model Execution Fabric relationship

`mary.llm.model_fabric` remains the top-level projection for compute suitability. The 13.60–13.64 provider evidence answers whether an authorized cloud/gateway route is healthy, available and worth spending quota on; 13.35+ task lanes answer whether a reachable model/node is suitable for realtime voice, conversation, coding, research, long-context or background work. Neither signal alone is promotion authority.

The intended decision vocabulary is:

`discovered -> configured -> authorized -> reachable -> feasible -> capable -> suitable -> preferred`

Each transition requires evidence appropriate to the boundary. "Free", "new", "large", or "uncensored" never means preferred by itself.

## Embeddings

Chat failover and embedding failover are deliberately different. Chat may switch models when policy permits. Stored vectors must remain in one compatible vector space for a given index. Mary's existing embedding identity/vector-index fingerprints remain authoritative; `embedding_router.py` is only a provider failover seam for exactly compatible embedding spaces.

## Catalog trust and provider substitution

A signed catalog can describe models, quotas, quirks and capabilities. It cannot install a model, add a secret, enable a provider, grant a permission, change creator policy, or alter identity/memory. Stale, expired, replayed, unpinned or badly signed catalog data is rejected.

Gateways may serve a different upstream provider/model than requested. Mary records served route identity as operational evidence and rejects unexpected substitution where exact identity matters, especially embeddings, explicit model requests, benchmarks and capability qualification. `unreported` is not proof of a match.

## What remains non-authoritative

Provider scores, quotas, health, readiness, catalogs, latency, TTFT, gateway route headers, endpoint discovery, benchmark results and embedding-provider availability are operational evidence. None are Mary memory, identity, relationship state, developed self, creator authority, permission state, or canonical goals.
