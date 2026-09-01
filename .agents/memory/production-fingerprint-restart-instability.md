---
name: Restart-stable preference loading
description: Durable developed-preference chronology must be preserved exactly during deserialization.
---

Treat a pre/post-deployment durable fingerprint mismatch as a hard stop even when
file count, total bytes, and CharacterSourcebook metadata remain unchanged.

**Why:** Preference deserialization once reconstructed durable overrides through
the normal mutation path, regenerating chronology timestamps in memory. A
graceful shutdown then persisted them, changing the fingerprint before any
creator turn. Matching aggregate sizes did not prove reconstruction equality.

**How to apply:** Keep load paths observational, preserve serialized chronology
exactly, test construct/close fingerprint equality, and stop deployment
acceptance whenever exact durable reconstruction disagrees.