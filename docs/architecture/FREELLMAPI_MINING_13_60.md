# FreeLLMAPI mining — MaryV2 13.60

Mary mines FreeLLMAPI as an engineering reference, not as identity authority.
The upstream project is a self-hosted OpenAI-compatible gateway with pooled
providers, health/cooldown accounting, quota ledgers, adaptive routing, prompt
compression, sticky sessions/context handoff, embeddings and operational
analytics.

## Patterns adopted

- quota/headroom is a first-class routing resource, alongside Mary's existing
  latency, correctness, hardware pressure and fit evidence;
- provider health and rate-limit pressure are ephemeral, content-free evidence;
- configured order remains authoritative when evidence is absent;
- upstream Retry-After/cooldown signals should be respected rather than hammered;
- one optional OpenAI-compatible gateway can represent many cloud providers;
- provider/gateway lanes remain replaceable and cannot own Mary identity,
  memory, relationship, goals or canonical state;
- private/local-only requests never become eligible for a cloud gateway merely
  because it has better quota;
- prompt compression/context handoff are prompt-projection concerns only; Mary
  already preserves canonical dialogue and creator constraints separately;
- analytics must be bounded and content-free at the routing layer;
- free-provider catalogs are volatile hints, not trusted executable policy.

## 13.60 implementation

`mary.llm.provider_pressure` adds a bounded process-local pressure ledger with
success/failure/rate-limit counts, latency EMA, optional quota headroom,
cooldown and a stable adaptive ordering function. No prompts, responses, API
keys or Mary state are retained.

`mary.llm.freellmapi` adds an optional adapter over Mary's existing
OpenAI-compatible transport. It is disabled unless
`MARY_FREELLMAPI_BASE_URL` is configured. Optional settings are
`MARY_FREELLMAPI_API_KEY` and `MARY_FREELLMAPI_MODEL` (`auto` by default).
This is intentionally a provider lane beneath Mary's router rather than a
replacement for Mary's router.

## Patterns already present from earlier Mary work

Mary already has several analogous or stronger controls: typed provider
capabilities/privacy/cost constraints, local-only routing, normalized failures,
Retry-After cooldown, bounded context projection, trailing-constraint
preservation, benchmark correctness/useful-throughput evidence, live node load,
resource fit, disposable specialists, capability evidence, and content-free
routing diagnostics. 13.60 should compose with these rather than duplicate
them.

## Deliberately not adopted

- no automatic import/storage of dozens of third-party API keys in Mary Core;
- no provider catalog update may grant capabilities or permissions;
- no blind 20-attempt failover chain for a character turn;
- no shared response cache for private conversation by default;
- no cloud route for local-only/private requests;
- no gateway owns canonical conversation/session continuity;
- no assumption that advertised free quota is durable or production-grade;
- no automatic ToS judgment: provider use remains operator-configured.

## Next integration seam

The pressure ledger should be wired into `LLMRouter` conservatively: only
adaptive free-cloud candidates should be reordered; explicit provider, private,
expert and creator session overrides remain authoritative. Successful attempts
feed latency/success evidence, rate limits feed cooldown/pressure, and future
provider adapters may feed bounded quota headroom. Unknown evidence must keep
the configured order.
