# Production Turn Failure Observability 13.2 — Test Report

## Result

The HTTP turn observability implementation passed its focused, affected, and
independent-review checks.

## Focused verification

Command:

```text
python -m pytest -q \
  tests/runtime/test_turn_failure_observability_13_2.py \
  tests/integration/test_canonical_lifecycle.py \
  tests/protocol/test_server_contract.py \
  tests/protocol/test_core_service.py \
  tests/protocol/test_client_contract.py \
  tests/llm/test_router_failover.py \
  tests/mobile/test_remote_core_mode_13_2.py
```

Result after lifecycle-aware correlation hardening: **33 passed** across the
final focused observability, Mobile, Core, client, and server selection.

Covered behavior includes:

- Mary-owned request-ID generation and HTTP response correlation;
- one-way correlation of upstream request IDs;
- secret-shaped and prose-shaped adversarial request IDs;
- no prompt, memory, sourcebook evidence, provider output, or credential in
  retained telemetry;
- bounded stage retention and bounded stage emission;
- successful canonical lifecycle coverage for context, sourcebook, memory,
  providers, fallback, dialogue, growth, and autonomy;
- provider timeout followed by successful fallback;
- provider exhaustion;
- measured canonical turn-lock wait;
- fail-soft post-processing telemetry while preserving a successful response;
- application exception classification with fixed safe HTTP detail;
- response-serialization failure classification and correlation;
- preservation of existing creator-auth HTTP status behavior;
- safe Core request-ID retention on Mobile success and HTTP failure;
- adversarial provider error/provenance removal from Mobile traces;
- ASGI cancellation classified as `upstream_disconnect`;
- suppression of late worker stages after disconnect completion;
- independently responsive health during a blocked active turn; and
- deterministic stage, total, and Mobile duration bounds.

## Affected regression verification

Command:

```text
python -m pytest -q \
  tests/protocol tests/runtime tests/llm tests/integration tests/mobile
```

Result: **527 passed**.

Compilation and diff hygiene:

```text
python -m compileall -q mary scripts tests
git diff --check
```

Result: **passed**.

## Full repository verification

Command:

```text
python -m pytest -q
```

Result: **1,411 passed, 1 skipped, 1 failed**.

The sole failure is the repository-structure gate detecting the active root
directories `data/` and `attached_assets/`. Neither directory is part of this
change. This task deliberately did not delete, move, or modify them because
the implementation must not alter Mary's data authority or `/data`.

## Independent review

An independent architecture/security review evaluated:

- content and credential leakage;
- request-correlation safety;
- telemetry bounds;
- exception and HTTP status behavior;
- `contextvars` propagation through `asyncio.to_thread`;
- lock-scope preservation;
- provider order/fallback semantics; and
- missing required stage/failure coverage.

The first review identified caller-controlled IDs, reflected runtime exception
details, and emission beyond the retention cap. Lifecycle-aware follow-up
review also identified missing upstream-disconnect classification, dropped
Mobile failure correlation, broad Mobile provenance retention, unvalidated
success IDs, and unbounded duplicate total durations. All were corrected and
received adversarial or concurrent regression tests.

The final independent review result was **PASS**, with no blocking or
high-severity correctness, privacy, or security issue in the production turn
observability scope.