---
name: Interaction preference evidence boundary
description: Trust and idempotency rules for durable creator interaction-preference learning.
---

Durable interaction preferences may learn only from direct creator instructions about Mary's responses or direct corrective feedback. Generated output, attributed or quoted text, guests, initiative, failed generations, contextual one-off requests, and retries are not evidence.

**Why:** Broad phrase matching and transport-local deduplication can turn quoted advice, provider fallback, or network retries into false durable preferences.

**How to apply:** Keep extraction bounded and positive, carry a stable creator-turn identity across transport boundaries, and check that identity across both active and decided preference evidence before counting it.