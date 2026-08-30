MARYV2 12.12.1 WINDOWS RESERVOIR LIFECYCLE HOTFIX

Purpose
-------
Fix Windows release-verification failures caused by disposable verifier runtimes
holding an open handle to the derived SQLite cognitive reservoir while
TemporaryDirectory cleanup attempts to remove it.

The real/canonical Mary runtime still uses the persistent reservoir.
Deterministic in-process release verifiers use an equivalent in-memory derived
reservoir, while dedicated tests continue to exercise persistent SQLite behavior.

Also hardens verifier application cleanup and adds lifecycle regression tests.

This hotfix does NOT modify .env, data/, memories, relationship state, API keys,
or MaryCosma.vrm.

Validated in packaging environment:
- full canonical suite: 757 passed, 1 skipped
- offline release pytest: 731 passed, 1 skipped
- diagnostics: 54/54 PASS
- complete deterministic/offline release gate: PASS
- previously failing provider_resilience: PASS
- relationship_development: PASS
- curiosity_development: PASS
- priority_grounding: PASS
