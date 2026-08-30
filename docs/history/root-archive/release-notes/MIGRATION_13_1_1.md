# MaryV2 13.1.1 Migration

13.1.1 is a code rebase/consolidation, not a new Mary and not a state reset.

1. Back up existing `.env` and `data/`.
2. Overlay the full 13.1.1 project source onto the existing MaryV2 repo.
3. Do not delete or replace the preserved `.env` or `data/`.
4. Run the 13.1 doctor, fast tests, full tests, and release gate.
5. Build the desktop frontend on the host.
6. Launch Mary and verify memory/relationship continuity before creating vectors or changing provider settings.
7. Commit the verified source with GitHub Desktop; GitHub synchronizes code, not Mary's live private state.
