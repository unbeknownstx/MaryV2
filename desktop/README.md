# MaryV2 Desktop 12.10 — Presence + Presentation Game Shell

The desktop is a presentation layer over the **same canonical `MaryApplication`** used by the terminal runtime. It does not create a second Mary, a second memory database, another relationship model, or another LLM router.

## What exists in this pass

12.10 retains the proven 12.7/12.8 VRM/chat ecosystem shell and the 12.9 runtime instrumentation, then adds Mary Home / Companion Pulse, stronger workspace-to-Presence connections, Focus-aware quiet behavior, Portrait Art presentation, and responsive UI polish:

- frameless game-like Mary window with custom title bar;
- left navigation rail: Chat, Memories, Personality, Studio, Study, Command, Focus, Stream, Gallery, Media, Voice & Avatar, Settings;
- central live `MaryCosma.vrm` stage using Three.js + `@pixiv/three-vrm`;
- geometry-based avatar framing with full / portrait / close modes;
- idle movement, blinking, mapped emotion expressions, TTS waveform lip-sync;
- persistent chat composer with typed barge-in and microphone/STT interruption handling;
- real dashboard state from Mary's emotion, memory, relationship, agency, provider, personality, values, and preference systems;
- memory highlights from current source-aware creator-profile state rather than fabricated cards;
- deterministic relationship-continuity index clearly labeled as a UI continuity metric, not a claim of human emotion;
- recent relationship/activity summaries;
- local music mini-player;
- command palette (`Ctrl+K`) with deeper Search, Research, Arcade, and Runtime/Latency workspaces;
- Studio shell for Unbeknownst and future project work;
- finite allowlisted creative-app integrations (Photoshop, Clip Studio, Krita, Blender, DaVinci Resolve, Audacity);
- Media shell with local audio and explicit YouTube search/open action;
- separate game-style launcher with PLAY button and optional SHA-256-verified staged update checks.

The approved visual target is preserved at:

```text
desktop/design/MARY_UI_TARGET.png
```

That image is a design target, **not** the UI implementation. The real screen is HTML/CSS/JavaScript + live VRM + Qt WebChannel and is intended to be tuned against that target during the personal-PC visual pass.

## Frontend stack

```text
PySide6 / Qt WebEngine
        ↓
Vite multi-page frontend
        ├── index.html        Mary application
        └── launcher.html     Mary Launcher
        ↓
Three.js + @pixiv/three-vrm
        ↓
Qt WebChannel
        ↓
canonical Python MaryApplication
```

No CDN, cloud font, or web framework is required to render the application shell. The only NPM runtime dependencies are pinned Three.js/VRM packages and Vite for building.

## Setup / rebuild

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

macOS:

```bash
bash scripts/setup_macos.sh
```

Manual frontend build:

```text
cd desktop
npm ci
npm run check
npm run build
cd ..
```

Vite produces both:

```text
desktop/dist/index.html
desktop/dist/launcher.html
```

Mary's VRM remains at:

```text
desktop/public/models/MaryCosma.vrm
```

## Run from source

Game-style launcher on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_launcher_windows.ps1
```

Direct Mary window, bypassing launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1
```

Generic development commands:

```text
python -m scripts.run_launcher
python -m scripts.run_desktop
```

## Build the Windows programs

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Expected build outputs:

```text
dist\MaryLauncher\MaryLauncher.exe
dist\MaryV2\MaryV2.exe
```

Normal use is `MaryLauncher.exe` → **PLAY MARY**. The launcher finds the sibling MaryV2 build.

## Real state versus UI presentation

The UI never invents the important cards. It reads:

- mood/intensity/arousal → `EmotionManager`;
- memory counts → `MemoryManager`;
- memory highlights → current source-aware creator profile;
- relationship label/index → relationship records/history/milestones;
- curiosities → `CuriositySystem`;
- traits → `Personality`;
- values → `Values`;
- preferences → `Preferences`;
- provider availability/effective route → `RuntimeEnvironment`;
- conversation status → authoritative desktop conversation state machine.

The frontend may render those values as bars/rings/labels, but their source remains MaryV2.

## Studio / Unbeknownst

The Studio screen is a live sandboxed project workspace in 12.8. It already defines the product shape and safe integration boundary, but it does **not** pretend it has imported the real manuscript yet.

Next personal-PC steps:

1. point `MARY_WORKSPACE_ROOT` at the desired private creative workspace;
2. define the actual Unbeknownst project folder structure;
3. index chapters/lore/characters as project resources rather than generic Mary memory;
4. add chapter editor + file save/revision history;
5. add Mary actions such as continuity pass, dialogue pass, lore check, storyboard context;
6. launch configured external tools for files that belong in Photoshop/Clip Studio/Blender/etc.

Do not embed arbitrary desktop programs by window-parenting unless there is a strong reason. Launching the real program and keeping Mary beside it is more robust.

## Media

12.7 supports local audio selection/playback through the UI and explicit browser opening for YouTube search. Future Watch Together can add an embedded video surface plus transcript/metadata grounding. Mary should never claim she watched a video unless the runtime actually supplied grounded media content/transcript information.

## Launcher update policy

The update system is optional and disabled until `MARY_UPDATE_MANIFEST_URL` is set. A manifest looks like:

```json
{
  "version": "12.8.0",
  "channel": "private-v2",
  "package_url": "https://example.com/MaryV2-12.8.0.zip",
  "sha256": "<64 hex characters>",
  "notes": "What changed"
}
```

The 12.7 launcher can check, download, hash-verify, and **stage** a newer package. Automatic replacement/rollback is deliberately not enabled until the versioned installation layout is validated on the personal PC. Persistent `data/` is always separate from staged updates.

## Failure isolation

Text conversation remains authoritative. Voice, avatar presentation, microphone input, a creative integration, the launcher update server, or an individual LLM provider may fail without being allowed to swallow Mary's text response or corrupt persistent state.
