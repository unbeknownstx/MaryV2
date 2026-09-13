# MaryV2 13.33 — Windows Validation — 2026-09-13

This record captures real-host validation performed on the Windows development machine after the 13.33 bounded cognitive execution work.

## Host validation

Repository structure:

```text
PASS canonical root is clean
PASS historical material is separated from active source
PASS mutable runtime state/dependency outputs are outside source
```

Focused 13.33 tests:

```text
tests/cognition/test_deliberation_executor_13_33.py
3 passed

tests/learning/test_strategy_advisor_13_33.py
2 passed
```

Compatibility regression check:

```text
tests/runtime/test_performance_hardening_13_8.py
1 passed
```

Full deterministic suite on commit `8829ba18b6d1f3b3e3d91fe68f952e76fa5ee7aa`:

```text
1908 passed
5 skipped
0 failed
1 third-party Starlette/AnyIO deprecation warning
```

## Research-convergence diagnostic

After commit `3b9263435c3e4c0dfd788a070cd4fa89e82d5da3` fixed direct script import bootstrapping, Windows successfully ran:

```text
MaryV2 research convergence: 13.32
deliberation: 13.33
memory policy: 13.30
trajectory telemetry: 13.31
duplex policy: 13.32
optional research runtimes ready: opentelemetry
automatic self-modification: disabled
```

The full 1908-test suite was run immediately before the script-only import-bootstrap commit; the latest script execution was then validated directly.

## Acceptance status

**Windows deterministic status: GREEN for 13.33.**

Remaining:
- live canonical-Core connectivity and real-turn validation;
- Windows node/Ollama/provider-routing checks;
- structural trajectory evidence on real executor-backed turns;
- exact-main validation on M1;
- optional-runtime benchmarks before promotion.
