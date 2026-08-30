# MaryV2 12.9 Verification Record

Verification was performed against an isolated copy of the uploaded MaryV2 project.
The uploaded archive and creator persistent state were not modified.

## Passed

- targeted 12.9 + regression set: **50 passed**
- complete repository Python suite: **697 passed, 1 skipped**
- consolidated deterministic/offline release gate: **PASS**
- release-gate deterministic pytest selection: **672 passed, 1 skipped**
- system diagnostics: **54 / 54 PASS, Healthy True**
- MaryV2 12.8 Ecosystem + Presence verifier: **PASS**
- MaryV2 12.9 Desktop Uplift verifier: **PASS**
- frontend JavaScript syntax check (`npm run check`): **PASS**

The release gate also passed memory restart, provider resilience/routing, self-introspection,
relationship learning, curiosity/priorities, emotion, desktop, voice input, conversation runtime,
continuity, context lifecycle, provider guarantees, persistence recovery, state integrity,
release hygiene, standalone readiness, and local tool-safety checks.

## Frontend bundle note

`npm run build` could not be completed in the packaging container because its copied frontend
`node_modules` did not contain Vite and `npm ci` timed out against the npm registry. This is the
same class of host dependency limitation already documented by the MaryV2 package. The 12.9
installer therefore performs `npm ci`, `npm run check`, and `npm run build` on the target Windows
PC before running the installed 12.9 verification. If that build fails, the installer stops and
reports the failure rather than calling the installation complete.

## State safety

The patch payload contains no `.env`, no provider credentials, and no `data/` creator state.
The installer refuses any payload path targeting `.env` or `data/`, backs up replaced source files,
and verifies SHA-256 hashes after copying.
