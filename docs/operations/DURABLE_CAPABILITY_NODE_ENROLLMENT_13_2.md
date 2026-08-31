# Durable Capability-Node Enrollment 13.2

## State boundary

Core's canonical node-enrollment file contains only:

- trusted node ID, enrollment timestamp, and a SHA-256 durable-proof digest;
- active one-time grant digests with bounded expiry/use metadata;
- bounded sanitized enrollment/reconnect/revocation audit events; and
- the latest numeric session generation for each node.

Raw enrollment grants, raw durable device proofs, session-token digests, registry
leases, capabilities, and device tasks are not durable state. A Core restart
reconstructs trust while intentionally discarding every active session and task.

Durable trust does not expire automatically. It remains valid until deliberate
creator re-enrollment rotates its proof or creator revocation removes it.

## Authentication and restart recovery

1. A creator issues a short-lived, use-limited grant bound to one exact node ID.
2. The node registers with that grant. Core persists a durable-proof digest
   before returning the raw proof and a new ephemeral session token.
3. The node stores the proof locally. Windows uses CurrentUser DPAPI under the
   interactive user that owns the Scheduled Task. POSIX nodes use a private
   `0700` directory and `0600` credential file.
4. Normal heartbeat, poll, completion, and disconnect calls use only the
   process-local session token.
5. After Core restart, the node registers over HTTPS with its durable proof.
   Core issues a new session token and generation. The old token cannot be used.

Core refuses all node registration over plaintext HTTP, including loopback.
The proof is sent only on registration and never appears in request JSON or
status. TLS-terminating deployments must configure their ASGI server to accept
forwarded scheme metadata only from the trusted reverse proxy.

## Replacement and revocation

A current live node can be refreshed only with its current session token. A
durable proof or enrollment grant cannot take over that live identity.

Deliberate creator/grant re-enrollment rotates the durable proof and session,
increments the generation, and expires all nonterminal work from the prior
session. Old proofs and session tokens then fail.

The creator-authenticated `POST /v1/nodes/revoke` operation removes durable
trust and grants for the named node, persists that removal, revokes the active
session, removes the registry lease, and expires pending work. The machine
cannot reconnect until the creator deliberately enrolls it again.

## Lifecycle interaction

Node authentication does not wake Mary and does not authorize execution.
SLEEPING and OFFLINE continue to reject task enqueueing and claiming. Waking a
creator surface does not alter trusted-device records or credential checks.

## Existing Windows-node migration

Existing node IDs are not silently trusted. Perform this once when physically
at the already-approved PC:

1. Confirm the existing `MARY_NODE_ID`, or use the PC's existing
   `COMPUTERNAME` fallback. Do not choose a replacement ID.
2. From creator-authenticated Core administration, issue one bounded enrollment
   grant for that exact node ID. Do not put the grant in chat, logs, or source.
3. On the PC, from the MaryV2 repository, run:

   `powershell -ExecutionPolicy Bypass -File scripts\migrate_windows_node_trust.ps1`

4. Paste the one-time grant into the hidden prompt. The script supplies it only
   to the child process, performs one registration, stores the durable proof
   with CurrentUser DPAPI, clears the process environment, and exits.
5. Remove any historical `MARY_NODE_ENROLLMENT_GRANT` entry from `.env` or the
   Windows user environment.
6. Start the existing Scheduled Task:

   `Start-ScheduledTask -TaskName "MaryV2 Windows Capability Node"`

7. Verify Core reports the same node ID, a connected lease, and fresh heartbeat.

No currently inaccessible PC was contacted or modified while implementing this
architecture. Actual DPAPI storage, Scheduled Task startup, and post-restart
heartbeat must still be verified on the physical Windows machine.