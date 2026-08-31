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
  tests/llm/test_router_failover.py
```

Result: **21 passed**.

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
- response-serialization failure classification and correlation; and
- preservation of existing creator-auth HTTP status behavior.

## Affected regression verification

Command:

```text
python -m pytest -q tests/protocol tests/runtime tests/llm tests/integration
```

Result: **490 passed**.

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

Result: **1,375 passed, 1 skipped, 1 failed**.

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

The first review identified three hardening issues: caller-controlled IDs,
reflected runtime exception details, and emission beyond the retention cap.
All three were corrected and received adversarial regression tests.

The follow-up review result was **PASS**, with no blocking or high-severity
issue in the explicit HTTP `POST /v1/turn` scope.