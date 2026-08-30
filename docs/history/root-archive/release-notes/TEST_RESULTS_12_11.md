# MaryV2 12.11 Test Results

Release: **12.11.0 — Fast Dialogue + Connected Presence + Neon Street Desktop**

## Canonical Python suite

```text
726 passed, 1 skipped
```

## Deterministic/offline release gate

```text
701 passed, 1 skipped
Diagnostics: 54 / 54 PASS
Healthy: True
All registered milestone verifiers: PASS
```

This includes retained 12.8 Ecosystem + Presence, 12.9 Desktop Uplift, 12.10 Presence + Presentation, and the new 12.11 verifier.

## 12.11 verifier

`python -m scripts.verify_connected_companion_12_11` — **PASS**

Verified surfaces include conversation lanes, latency-aware reflection policy, purpose-specific fast Groq conversation model, local style repair, explicit YouTube search adapter, loopback read-only WebSocket transport, desktop media/presence wiring, workspace launcher, ambient audio, blue-neon street clarity layer, and repository agent guidance.

## WebSocket live smoke

A real loopback server was started with `websockets 16.0` on a temporary port. Verified:

- server start
- hello/display-safe snapshot
- ping/pong
- explicit snapshot request
- server-pushed `turn_trace` event
- clean shutdown

## OpenAI expert bridge

The no-spend install verifier passed. Paid OpenAI remains excluded from `free_first`, the expert route selects OpenAI only when explicitly requested/authorized, private/offline continues to force Ollama, and expert output remains task-local advisory evidence.

No paid OpenAI live inference was used during packaging.

## Frontend

Node syntax verification passed for:

- `desktop/src/main.js`
- `desktop/src/launcher.js`
- `desktop/src/runtime/turnTrace.js`
- `desktop/src/ui/presenceHome.js`
- `desktop/vite.config.js`

The packaging container does not contain the npm dependency tree required to execute Vite itself. `SETUP_WINDOWS_12_11.ps1` therefore performs `npm ci`, `npm run check`, and `npm run build` on the target Windows PC and stops on failure. The creator's preceding 12.10 Windows host successfully built with Vite 8.2.1.

## Private-state safety

The distributable intentionally excludes `.env`, `data/`, `.venv`, `node_modules`, `.git`, generated `desktop/dist`, caches, installer payloads, and repository-local upgrade backups.
