# Creator-Surface Lifecycle 13.2

## Purpose

Mary sleeps when no authenticated creator surface is present without taking
Mary Core offline. Core remains reachable for health, authentication,
lifecycle inspection, surface lease operations, wake, and authorized lifecycle
control.

The lifecycle coordinator is owned by the canonical `MaryCoreService`. It is
process-local and intentionally not persisted. A Core restart starts with an
empty lease registry and therefore reports Mary as `SLEEPING` until a creator
surface registers.

## States

| State | Meaning | Execution |
| --- | --- | --- |
| `ACTIVE` | At least one lease has recent meaningful creator activity | Allowed |
| `IDLE` | A lease remains live, but meaningful activity is outside the active grace period | Allowed |
| `SLEEPING` | No lease is live, or inactivity reached the sleep threshold | Gated |
| `OFFLINE` | Creator explicitly placed Mary offline | Gated |

Heartbeats renew lease expiry but do not count as meaningful activity.
Foreground/wake and explicit interaction do count as activity.

`OFFLINE` is never inferred. Registration, renewal, wake, and ordinary turns do
not clear it. Only the authenticated explicit online/offline control can change
that flag.

## Protocol

All lifecycle routes require the existing creator bearer authentication.

| Method and route | Purpose |
| --- | --- |
| `GET /v1/creator-surfaces/status` | Inspect Mary lifecycle and bounded lease metadata |
| `POST /v1/creator-surfaces/register` | Register one creator surface lease |
| `POST /v1/creator-surfaces/renew` | Renew expiry and optionally report visibility/activity |
| `POST /v1/creator-surfaces/visibility` | Update visible/foreground state |
| `POST /v1/creator-surfaces/disconnect` | Retire one surface lease |
| `POST /v1/creator-surfaces/wake` | Wake an existing lease; cannot override `OFFLINE` |
| `POST /v1/creator-surfaces/offline` | Explicitly set Mary offline or online |

Surface IDs are bounded transport identifiers. The Mobile UI creates one
session-scoped ID per browser tab/native web view and sends it on every
lifecycle operation. Closing one tab therefore cannot retire another tab's
lease.

## Runtime behavior

- Lease expiry is evaluated by a Core-owned daemon timer, not only when another
  request happens.
- Lifecycle/autonomy transition bookkeeping is serialized under one Core lock.
- The coordinator pauses autonomy only when the existing autonomy runtime is
  running, and resumes only a pause it owns.
- Core health remains independent of Mary lifecycle. Operators and clients must
  display Core `reachable`/`unreachable` separately from Mary
  `ACTIVE`/`IDLE`/`SLEEPING`/`OFFLINE`.
- Wake preserves the same application, Mary object, durable state, and
  relationship continuity.

## Execution boundaries

While `SLEEPING` or `OFFLINE`, Core denies new:

- canonical turns;
- proactive presence pulse and idle-tick work;
- provider generation, including direct provider probes;
- tool execution;
- capability-task enqueue/dispatch; and
- capability-task poll/claim.

Provider, tool, or node work that already crossed its execution boundary is not
interrupted. Capability-task completion remains available so already-running
device work can report its terminal result.

## Recovery

1. Confirm Core reachability with `GET /v1/health`.
2. Inspect `GET /v1/creator-surfaces/status`.
3. If `SLEEPING`, register or renew the returning surface, then wake that same
   surface ID.
4. If `OFFLINE`, use the authenticated offline control with `offline: false`,
   then register/wake a surface.
5. Do not restart Core merely to wake Mary. Restarting clears all leases and
   intentionally returns Mary to `SLEEPING`.

Lease records contain no prompt, response, memory, evidence, credentials, or
durable character state.