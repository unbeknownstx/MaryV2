# Migration to MaryV2 13.2

1. Keep `.env`, `data/`, memories, relationship state, developed-self state, and private voice IDs out of Git commits.
2. Apply the 13.2 code overlay on branch `13.2-unified-runtime`.
3. Install updated requirements.
4. Run `python -m pytest tests/protocol -q`.
5. Run the normal targeted host checks; use the full suite only as a release gate.
6. Set `MARY_CORE_TOKEN` before launching Core.
7. For cloud deployment, point `MARY_DATA_DIR` at durable mounted storage and run exactly one Core replica.
8. Do not copy old Mac/Windows/Replit state into the new live directory yet. Archive it for selective migration.
9. Frontends migrate by replacing local Mary construction with `MaryClient`/Mary Protocol calls. The backend remains the same when a native iOS app replaces the Replit frontend.
