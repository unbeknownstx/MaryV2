---
name: Capability-node session isolation
description: Security invariant for scoped node credentials, lease changes, and device-task ownership.
---

Node credential validation and rotation, registry lease transitions, and device-task claim/completion/expiry must be linearized through one shared lifecycle boundary. Re-enrolling a stale or disconnected stable node ID must expire every nonterminal task from the prior session before issuing replacement credentials or making the node live. A stale heartbeat must never revive an expired session; it must force grant-authorized re-enrollment and generation rotation.

Enrollment authority is separate from creator authority. Grants must be node-ID-bound, expiring/use-limited, and persisted only as digests with bounded audit metadata so recovery survives Core restarts without retaining creator credentials or raw secrets.

**Why:** Separate locks or node-ID-only task ownership allow disconnect races, obsolete long polls, or a replacement process to receive private task context created for an earlier session. Header-presence checks and in-memory-only grant records can respectively permit unauthorized bootstrap or break legitimate restart recovery.

**How to apply:** Any node-auth, registry, broker, long-poll, or recovery change must preserve scoped per-node credentials, verify an explicit authority mode rather than header presence, revalidate credentials and liveness on wake, and prevent queued or claimed work from crossing enrollment sessions.