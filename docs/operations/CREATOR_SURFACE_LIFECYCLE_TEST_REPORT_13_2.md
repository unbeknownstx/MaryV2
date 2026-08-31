# Creator-Surface Lifecycle 13.2 — Test Report

## Result

The creator-surface lifecycle implementation passed focused, affected, full
repository, static, and independent architecture/security review.

## Focused verification

Focused groups covered:

- deterministic `ACTIVE` → `IDLE` → `SLEEPING` transitions;
- zero leases, abrupt expiry, and multiple independent surfaces;
- bounded surface registration;
- explicit `OFFLINE` authorization semantics;
- timer-driven sleep without an observing request;
- atomic concurrent autonomy transitions;
- same-instance wake and owned pause/resume;
- sleeping/offline turn and proactive-presence denial;
- provider, tool, dispatch, and claim execution gates;
- completion of already-claimed node work;
- authenticated protocol contracts;
- per-tab Mobile lease identity and lifecycle forwarding; and
- identical web/native JavaScript bundles.

Result across the final review-focused groups: **58 passed**.

The completion review additionally required remote Terminal/Desktop
presentation coverage. The dedicated gateway, Terminal authority, Desktop
remote-Core, and node-only authority group passed **15 tests**, including:

- first remote turn from an initially sleeping presentation path;
- register and wake ordering before turn dispatch;
- stable bounded gateway surface identity;
- heartbeat renewal that does not report creator activity;
- clean Terminal/Desktop disconnect;
- node-only gateway exclusion; and
- deterministic turn/close serialization with disconnect last.

## Affected regression verification

The final combined runtime, Desktop, protocol, Mobile, canonical lifecycle,
distributed execution, provider routing, and tool integration regression
passed:

```text
300 passed
```

Compilation and static hygiene also passed:

```text
python -m py_compile ...
node --check mobile_web/app.js
cmp -s mobile_web/app.js mobile_native/MaryMobile/www/app.js
git diff --check
```

## Full repository verification

Command:

```text
python -m pytest -q
```

Result: **1,405 passed, 1 skipped, 1 failed**.

The sole failure is the known unrelated repository-structure gate detecting
the active root directories `attached_assets/` and legacy `data/`. Neither is
part of this change, and this task deliberately did not move or delete them.

## Independent review

An independent architecture/security review checked:

- canonical Core authority and non-persistence of leases;
- automatic expiry without incoming traffic;
- autonomy pause/resume ownership and transition races;
- explicit-only `OFFLINE`;
- provider, tool, proactive-presence, dispatch, and claim bypasses;
- in-flight work behavior;
- Mobile multi-tab/native surface isolation;
- creator authentication;
- Core reachability versus Mary lifecycle presentation; and
- preservation of capability-node credential/session isolation.

The first review identified timer, multi-surface identity, proactive idle,
transition serialization, and nested tool-registry wiring gaps. All were fixed
and covered by regression tests. Completion review then identified missing
Terminal/Desktop lease ownership, and follow-up review identified a concurrent
turn/close lease-resurrection race. The shared remote gateway now owns those
leases and serializes accepted turns against close; both findings have
deterministic regression coverage.