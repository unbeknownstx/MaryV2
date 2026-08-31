---
name: Capability-node session isolation
description: Security invariant for scoped node credentials, lease changes, and device-task ownership.
---

Node credential validation and rotation, registry lease transitions, and device-task claim/completion/expiry must be linearized through one shared lifecycle boundary. Re-enrolling a stale or disconnected stable node ID must expire every nonterminal task from the prior session before issuing replacement credentials or making the node live.

**Why:** Separate locks or node-ID-only task ownership allow disconnect races, obsolete long polls, or a replacement process to receive private task context created for an earlier session.

**How to apply:** Any node-auth, registry, broker, long-poll, or recovery change must preserve scoped per-node credentials, revalidate credentials and liveness on wake, and prevent queued or claimed work from crossing enrollment sessions.