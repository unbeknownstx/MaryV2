---
name: Capability-node trust and session isolation
description: Security invariant for durable device trust, ephemeral sessions, lease changes, and device-task ownership.
---

Node credential validation and rotation, registry lease transitions, and device-task claim/completion/expiry must be linearized through one shared lifecycle boundary. Re-enrolling a stale or disconnected stable node ID must expire every nonterminal task from the prior session before issuing replacement credentials or making the node live. A stale heartbeat must never revive an expired session; it must force grant-authorized re-enrollment and generation rotation.

Enrollment authority is separate from creator authority. Grants must be node-ID-bound, expiring/use-limited, and persisted only as digests with bounded audit metadata so recovery survives Core restarts without retaining creator credentials or raw secrets.

Durable device trust is separate from process-local node sessions. Core may persist only a versioned, node-bound proof digest and bounded metadata; raw durable proofs belong in OS-protected local storage. Every reconnect after Core restart must mint a fresh session generation. Registration credentials require HTTPS, including first enrollment. Revocation must durably remove trust before tearing down process-local state.

**Why:** Separate locks or node-ID-only task ownership allow disconnect races, obsolete long polls, or a replacement process to receive private task context created for an earlier session. Header-presence checks and in-memory-only grant records can respectively permit unauthorized bootstrap or break legitimate restart recovery. Treating a durable proof as a normal environment variable or allowing plaintext bootstrap exposes a reusable impersonation credential.

**How to apply:** Any node-auth, registry, broker, long-poll, recovery, or credential-storage change must preserve scoped per-node credentials, verify an explicit authority mode rather than header presence, commit durable trust changes before session activation, revalidate credentials and liveness on wake, and prevent queued or claimed work from crossing enrollment sessions.