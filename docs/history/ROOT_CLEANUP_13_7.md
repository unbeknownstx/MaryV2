# MaryV2 13.7 active-root documentation cleanup

13.7 removes several dated patch/install/report files from the active repository root. Their contents remain permanently available in Git history; retaining them beside `README.md` made it too easy for a human or coding agent to treat obsolete package instructions as current architecture.

Removed from the active root:

- `NEXT_MAC_STEPS.md` — superseded Mac boot/platform readiness instructions.
- `PACKAGE_STATUS.txt` — package-era status snapshot, not runtime authority.
- `README_PATCH.md` — safe-renderer patch note already converged into current source/tests.
- `TEST_RESULTS.txt` — stale point-in-time test count; CI is the current evidence.
- `SYNTHESIS_UPGRADE_2026-09-01.md` — dated upgrade narrative superseded by current architecture/research docs.

Files such as license/build specs and genuinely active runtime configuration remain at root. Historical removal is documentation hygiene only and does not delete Git provenance or Mary continuity state.

Current documentation entry points are `README.md`, `MARY_ROOT.md`, `docs/README.md`, `docs/architecture/SYSTEM_REGISTRY.md`, and `AGENTS.md`.
