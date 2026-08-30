# MaryV2 12.12.3 Production Hybrid Dialogue — Consolidated Verification

This milestone remains a required foundation under MaryV2 13.1.1.

Its production invariants are retained:

- deterministic LocalComposerV2 for eligible low-risk local dialogue;
- zero provider calls on accepted local turns;
- canonical-owner confirmation before authority-bearing local answers;
- fail-closed escalation for incomplete, stale, forged, or ambiguous derived records;
- bounded/redacted local diagnostics and traces;
- process-local bounded phrase history;
- isolated benchmark/test state that never reads or writes Mary's live private data;
- cloud-first task/general routing and local-first personal conversation routing remain distinct;
- paid OpenAI remains explicit expert-only.

13.1.1 rebase verification runs the original 12.12.3 targeted suites together with
13.0/13.1 development, realtime, mobile, retrieval, node, perception, and training
infrastructure. See `MARYV2_13_1_1_VERIFICATION.txt` for the consolidated result.
