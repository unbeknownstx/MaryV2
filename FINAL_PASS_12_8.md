# MaryV2 12.8 — Ecosystem + Presence First Program Pass

## Core result

12.8 is a consolidated successor to the validated 12.7 Desktop Game Shell. It keeps the existing MaryV2 identity/memory/relationship/cognition/provider architecture and adds modular workspaces around that same Mary instance.

## Added in 12.8

- Ecosystem manager bound to Mary's canonical private data root.
- Command Center: tasks, projects, goals, waiting items, ideas.
- Focus With Mary: persistent co-working timer state.
- Study Partner: persistent study projects + basic spaced repetition.
- Mary Inbox: non-interrupting bounded notices.
- Personal Search: bounded search over approved roots only.
- Research Notebook.
- Mary Arcade local mini-game surface.
- Runtime latency metrics.
- Skills/capability registry.
- Presence typed context bus.
- Initiative policy with silence as a valid action.
- Persistent pending thoughts.
- Cheap local idle actions/sounds/phrases.
- Windows foreground-window title observation (no screenshot).
- Visual-context raw frame stripping boundary.
- Twitch/OBS policy scaffolds, disabled by default.
- Local-first TTS: Piper when configured, otherwise Windows SAPI on Windows; cloud fallback opt-in.
- Optional faster-whisper STT support; Groq remains the easy first-boot STT.
- 12.8 game-shell workspaces and command-palette actions.
- Original boot sequence, UI sound set, holographic/ambient polish, ecosystem inspector card.
- Dedicated 12.8 release verifier and new regression/adversarial tests.

## Verification at freeze

- `python -m pytest -q`: **660 passed, 1 skipped**.
- Mary diagnostics: **54/54 PASS, Healthy True**.
- `python -m scripts.run_release_verification --offline`: **PASS**.
- 12.8 Ecosystem + Presence verifier: **PASS**.
- Release hygiene: **PASS**.
- Standalone readiness: **PASS**.
- Repository `data/` after verification: **absent**.
- `node --check` / `npm run check`: **PASS**.

## Host-build limitation

The packaging environment's npm registry access timed out during `npm ci`; Vite itself was therefore not available to perform the final production bundle here. `npm run check` passed. `scripts/build_windows.ps1` performs a fresh host-native `npm ci`, `npm run check`, `npm run build`, final preflight, full release verification, then PyInstaller for `MaryV2.exe` and `MaryLauncher.exe`.

## External features policy

Twitch, OBS, visual screen awareness, Ren'Py and other outside integrations remain optional/disabled by default for the first live PC boot. Their architecture/hooks can be expanded only after the local Mary desktop is stable.

## First-program polish freeze

- Added project-created HUD SVGs, custom cursors, mode-specific backgrounds, scan/presence animation layers, and launcher polish.
- Added `scripts/first_boot_windows.ps1` for a conservative one-pass Windows baseline.
- External Twitch/OBS/Vision/Ren'Py skills remain disabled by default for first boot.
- Final canonical result after polish: **660 passed, 1 skipped; diagnostics 54/54; offline release verification PASS**.
