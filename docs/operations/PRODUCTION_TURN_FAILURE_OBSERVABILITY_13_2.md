# Production Turn Failure Observability 13.2

## Scope

Mary Core now emits bounded, content-free telemetry for HTTP `POST /v1/turn`.
The recorder follows the existing canonical turn through the worker thread and
instruments existing owners; it does not add another turn orchestrator,
runtime, identity authority, or persistence authority.

Provider order, provider timeouts, fallback behavior, canonical state
ownership, proposal-only autonomy, and application lifecycle behavior are
unchanged.

## Correlation

Every HTTP turn receives a Mary-owned `request_id`. The same value is:

- emitted on every retained stage record;
- emitted on the completion record;
- returned in `X-Mary-Request-ID`;
- returned in `TurnResponse.request_id`; and
- retained in Core's bounded recent-trace ring.

If Railway or another proxy supplies `X-Request-ID`,
`X-Railway-Request-ID`, or `X-Correlation-ID`, Mary records only a 24-character
SHA-256 `upstream_request_hash`. The caller-controlled header is never logged
or reflected. Operators can hash a known upstream ID to correlate it without
placing the original value in Mary's telemetry.

Each completion record also includes `core_instance_id` and
`core_uptime_ms`. A new `mary.core.started` event, a changed instance ID, or
low uptime after an interrupted request provides evidence of a process
restart. A process killed before it can emit a completion record cannot report
its own termination cause; Railway runtime logs remain authoritative for OOM,
forced termination, and infrastructure events.

## Stage records

| Stage | Existing owner | What the timer covers |
| --- | --- | --- |
| `core_ingress` | Protocol server | Creator authentication and request parsing |
| `turn_lock_acquisition` | Core service | Wait to acquire the canonical turn lock |
| `application_turn` | Core service | Existing canonical application invocation |
| `context_construction` | Mary | Canonical context construction |
| `character_sourcebook_retrieval` | Turn mind | Authored source selection and prompt projection |
| `memory_retrieval` | Mary | Canonical memory-context retrieval |
| `provider_availability` | LLM router | Per-provider resolution and availability check |
| `provider_generation` | LLM router | Existing provider call, with its existing timeout |
| `provider_fallback` | LLM router | Fallback transition, no-fallback skip, or exhaustion |
| `dialogue_persistence` | Mary | Existing response record and dialogue completion |
| `growth_processing` | Mary | Existing fail-soft growth observation |
| `autonomy_processing` | Application | Existing idempotent startup or one passive cycle |
| `response_serialization` | Protocol server | `TurnResponse` conversion to the HTTP payload |

Stage records contain only:

- schema and event names;
- Mary request ID and optional upstream request hash;
- Core instance ID and bounded turn ID;
- allowlisted stage and status;
- elapsed milliseconds and sequence;
- bounded provider name and attempt number where applicable;
- bounded outcome;
- allowlisted failure category; and
- exception class name, never the exception message.

No prompt, memory, sourcebook evidence, provider output, dialogue text,
character evidence, credential, authorization header, or exception message is
recorded.

## Failure categories

| Category | Meaning |
| --- | --- |
| `provider_timeout` | A provider attempt raised a timeout-class exception |
| `provider_error` | A provider attempt failed for another normalized reason |
| `provider_exhausted` | No provider produced an acceptable response |
| `application_exception` | The canonical application turn failed |
| `lock_failure` | Canonical turn-lock acquisition failed |
| `post_processing_failure` | Dialogue, growth, or autonomy failed after/beside generation |
| `serialization_failure` | The Core response could not be converted to its HTTP payload |
| `authentication_failure` | Creator authentication failed at ingress |
| `invalid_request` | Request parsing or validation failed |

Fail-soft post-processing remains fail-soft. A successful creator response can
therefore have a failed dialogue, growth, or autonomy stage and still end with
an overall successful completion record. This makes the partial failure
visible without changing the successful response.

## Bounds

- A trace retains and emits at most 64 stage records.
- The configured cap is clamped to 16–128.
- Additional stage records are not emitted and increment
  `dropped_stage_count`.
- Core retains the 40 most recent completed trace snapshots in memory.
- Identifiers, labels, provider names, attempt numbers, exception class names,
  durations, and outcome values are length/range bounded.
- Traces are process-local diagnostics and are not written into Mary's
  canonical durable state.

## Sanitized examples

Provider timeout followed by fallback:

```json
{"attempt":1,"core_instance_id":"core-a","elapsed_ms":20001.42,"error_type":"TimeoutError","event":"mary.turn.stage","failure_kind":"provider_timeout","provider":"primary","request_id":"request_a1b2","schema":1,"sequence":6,"stage":"provider_generation","status":"failure"}
```

Provider exhaustion:

```json
{"attempt":2,"core_instance_id":"core-a","elapsed_ms":0.0,"error_type":"LLMProviderError","event":"mary.turn.stage","failure_kind":"provider_exhausted","outcome":"exhausted","provider":"secondary","request_id":"request_a1b2","schema":1,"sequence":10,"stage":"provider_fallback","status":"failure"}
```

Fail-soft growth failure with a successful overall turn:

```json
{"core_instance_id":"core-a","elapsed_ms":1.12,"error_type":"RuntimeError","event":"mary.turn.stage","failure_kind":"post_processing_failure","request_id":"request_a1b2","schema":1,"sequence":12,"stage":"growth_processing","status":"failure"}
{"core_instance_id":"core-a","core_uptime_ms":42301.8,"dropped_stage_count":0,"event":"mary.turn.complete","outcome":"success","request_id":"request_a1b2","schema":1,"stage_count":15,"total_elapsed_ms":684.31}
```

The examples use invented identifiers and timings and contain no production
request data.