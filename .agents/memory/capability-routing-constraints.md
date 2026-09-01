---
name: Capability routing constraints
description: Durable safety rule for routing generated reasoning across replaceable providers.
---

Capability constraints must fail closed at the common routing boundary. Privacy, deadline, structured-output, cost, and operation fields are enforcement inputs, not observational metadata.

**Why:** A caller-controlled “redacted” flag, a deadline checked only after a blocking call, or JSON mode without response validation can look governed while still disclosing context, blocking workers, or accepting malformed results.

**How to apply:** Bind redaction evidence to the exact outbound content, advertise only capabilities a provider adapter really enforces, validate constrained responses after generation, and keep tools, audio, research retrieval, and device actions on their own typed boundaries.