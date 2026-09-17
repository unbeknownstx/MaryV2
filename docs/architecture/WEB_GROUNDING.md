# MaryV2 Web Grounding

Mary already has a first-class external-evidence path. This document records the
current ownership boundary, canonical search-provider ownership, and optional
local-first routing used by the grounding layer.

## Authority boundary

Web retrieval is a capability, not an authority.

```text
creator turn
  -> intent detection
  -> ToolRegistry web_search / web_fetch
  -> mary.tools.web provider
  -> Researcher
  -> SourceResolver
  -> ResearchGrounder
  -> Evaluator
  -> temporary relevant_knowledge
  -> EvidenceValidator grounded synthesis
  -> user-facing answer + source footer
```

The canonical Mary Core remains the identity/state authority. Search providers,
web pages, snippets, and extracted content remain untrusted external evidence.
They do not become memory, personality, creator truth, or self-state simply
because a model saw them.

`web_search` and `web_fetch` remain `APPROVAL_REQUIRED` ToolRegistry operations.
An explicit creator search request can be approved for that exact request by the
application coordinator; an inferred current-information need still creates a
scoped pending request. No search backend introduced here changes that rule.

## Existing evidence contract

`mary.learning.evidence.EvidenceValidator` gives researched turns a stricter
contract than ordinary model conversation:

- use only approved research evidence;
- support factual claims with supplied evidence;
- prefer primary/official evidence when sources disagree;
- do not strengthen source wording;
- treat snippets/excerpts as incomplete;
- disclose insufficient or conflicting evidence instead of guessing;
- for dynamic questions, prefer the newest strong evidence;
- do not use outside parametric model knowledge as a substitute for retrieval.

That is the canonical place for evidence-synthesis behavior. Do not create a
second independent `web_grounding` brain or let a provider own source truth.

## Search ownership

Concrete general-web providers are owned by `mary.tools.web` and share the same
`SearchResult` / `WebClient` interface:

- `tavily` — default structured search backend;
- `brave` — optional Brave Search API backend;
- `searxng` — creator-configured SearXNG JSON backend.

`create_search_provider()` supports all three concrete providers directly.
`MARY_SEARCH_PROVIDER` may select one of them without changing ToolRegistry
permissions.

`mary.tools.search_backends` owns only multi-provider routing. `local_first`
(alias `auto`) tries configured backends in this order:

```text
SearXNG -> Tavily -> Brave
```

The fallback chain skips backends that are not configured. A configured backend
that errors or returns no results may fall through to the next configured
backend. Failures retain only display-safe backend/error-type metadata; secrets
are never copied into result metadata.

### SearXNG configuration

```bash
MARY_SEARCH_PROVIDER=searxng
MARY_SEARXNG_URL=http://127.0.0.1:8080
```

SearXNG must expose its JSON search format. Mary sends a normal GET search to
`/search` with `format=json`. The base URL must be HTTP(S), include a hostname,
and must not contain embedded credentials, a query, or a fragment.

### Local-first configuration

```bash
MARY_SEARCH_PROVIDER=local_first
MARY_SEARXNG_URL=http://127.0.0.1:8080   # optional
TAVILY_API_KEY=...                        # optional
BRAVE_API_KEY=...                         # optional
```

At least one backend in the chain must be configured. No API key is required for
SearXNG itself when the creator operates the service locally.

## Knowledge gateway separation

`mary.knowledge.gateway` remains the bounded encyclopedic/academic gateway for
sources such as Wikipedia, OpenAlex, Crossref and Semantic Scholar. Its legacy
`SearXNGAdapter` remains importable for backward compatibility, but is not in the
default adapter list.

This avoids exposing the same configured SearXNG service simultaneously through
both `web_search` and `knowledge_search` as two separately approved general-web
routes. General web retrieval has one default owner: `mary.tools.web`.

## Evidence-backed corrections

An evidence-backed creator correction is precision-sensitive. The response-risk
layer exposes a `user_correction_with_evidence` authority signal so a correction
that has already been grounded upstream cannot be downgraded to the
`SOCIAL_LOW_RISK` fast path simply because its wording is conversational.

This signal is routing metadata, not evidence. It cannot manufacture support for
a claim, bypass web/tool approval, or overwrite memory. Hard tool/deep-reasoning
requirements still outrank it.

## Why this is not a second grounding subsystem

Search backends retrieve candidates only. Existing Mary owners still perform
source resolution, ranking, evaluation, bounded knowledge injection, evidence
synthesis, learning promotion policy, and source attribution. This keeps the
one-Mary architecture intact and makes search replaceable infrastructure rather
than identity or truth authority.

## Verification targets

The focused regression suite should verify:

1. SearXNG environment configuration and base-URL validation.
2. `create_search_provider("searxng")` selects the native web provider.
3. SearXNG JSON result normalization into `SearchResult`.
4. Local-first fallback behavior and display-safe route metadata.
5. The default KnowledgeGateway does not expose a second SearXNG route.
6. ToolManager can select SearXNG while `web_search` remains external,
   read-only, and `APPROVAL_REQUIRED`.
7. Evidence-backed corrections cannot be classified as low-risk social turns.
8. Evidence synthesis retains its evidence-only, source-conflict, and
   current-information rules.
