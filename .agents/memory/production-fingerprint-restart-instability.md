---
name: Production fingerprint restart instability
description: A production deployment and rollback both changed the durable-state fingerprint before any acceptance turn.
---

Treat a pre/post-deployment durable fingerprint mismatch as a hard stop even when
file count, total bytes, and CharacterSourcebook metadata remain unchanged.

**Why:** A controlled deployment changed the fingerprint before any live
acceptance turn, and rolling back to the known-good code tree changed it again.
This shows startup can mutate fingerprint-relevant state; matching aggregate
sizes does not prove reconstruction equality.

**How to apply:** Stop acceptance, execute the approved code rollback, avoid
creator or learning turns, and diagnose the per-file/projection difference from
verified backups before attempting another production deployment.