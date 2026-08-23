# MaryV2 12.10 — Presence Fabric + Companion Home + Presentation Polish

This is a forward iteration of the tested MaryV2 12.9 runtime. It does **not** replace Mary's identity, memory, relationship, personality, agency, provider abstraction, VRM pipeline, or canonical persistent-state rules.

The intended Windows repository remains exactly:

```text
C:\Users\Melvin\Documents\GitHub\MaryV2
```

There is no alternate "clean project" runtime directory in 12.10.

## What 12.10 adds

### Mary Home / Companion Pulse

The Desktop now has a Home surface that combines small **read-only** summaries from existing authoritative systems:

- Command Center
- Study
- Focus
- Mary Inbox
- Presence pending thoughts
- represented Mary curiosity
- current relationship/emotion/runtime state

`mary/ecosystem/companion.py` does not persist a new `companion.json`, make autonomous plans, or promote data into memory. It is a bounded display view over the state owners that already exist.

### Stronger workspace → Presence connections

Creator-approved desktop actions now publish typed live-context events into the existing bounded Presence bus:

- `COMMAND_CHANGED`
- `STUDY_CHANGED`
- `FOCUS_CHANGED`
- `CREATIVE_CHANGED`

These events are environmental/workspace context, not creator/system instructions. Silence remains a valid decision and Focus events are specifically downweighted.

### Focus quiet behavior

While Focus is active, cheap local avatar animations may continue, but Presence idle selection suppresses idle sounds and tiny idle phrases. This makes Focus affect Mary's actual desktop behavior instead of being only a timer.

### Presentation modes

The working `MaryCosma.vrm` pipeline remains primary and unchanged in authority. Voice & Avatar now also offers a local **Portrait Art** presentation mode using Mary's packaged reference artwork. This is a UI choice only; it does not change Mary's identity or backend state.

### Desktop polish

12.10 adds:

- a cinematic Mary Home hero
- a right-rail Companion Pulse card
- focus-aware desktop chrome
- additional responsive laptop/low-height rules
- tighter cross-navigation between workspaces
- Vite 8 `import.meta.dirname`
- Rolldown vendor/Three/VRM code-splitting configuration

The production bundle is rebuilt on the real Windows host by the canonical setup script.

## Windows setup / verification

From the canonical repository root:

```powershell
cd C:\Users\Melvin\Documents\GitHub\MaryV2
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS_12_10.ps1
```

That script:

1. reuses or creates `.venv`
2. installs Python dependencies
3. runs `npm ci`
4. runs frontend syntax checks
5. builds the production Vite frontend
6. runs 12.9 + 12.10 targeted regressions
7. runs the 12.10 verifier
8. runs the complete canonical Python suite
9. runs the deterministic/offline release gate
10. checks repo-local state integrity when applicable

For normal development after setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
```

Before a meaningful checkpoint:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_full.ps1
```

Before packaging/release:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_release.ps1
```

## Launch

Direct desktop:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1
```

Launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\launch_launcher_windows.ps1
```

## Private state

The distributable source package intentionally contains no private `.env` and no personal `data/` tree.

On the personal Windows host, preserve the existing private `.env` and the canonical Desktop state under `%LOCALAPPDATA%\MaryV2\data`. Tests and release verification remain isolated from that real state.
