# MaryV2 12.7 — Desktop Game Shell / Home-PC Build Candidate

## Purpose

12.7 is the bridge between the frozen/stable V2 backend and the final visual/product pass on the personal PC. It deliberately does **not** rebuild Mary's cognition, memory, personality, relationship, agency, tool, or provider architecture. Instead it gives those systems a game-like presentation surface and a launcher/distribution boundary.

## Visual target

The target screenshot approved during development is stored at:

```text
desktop/design/MARY_UI_TARGET.png
```

The target language is:

- near-black/navy base;
- neon pink/magenta primary accent;
- purple/violet secondary accent;
- cyan/electric-blue system accent;
- translucent glass panels;
- glowing one-pixel borders;
- Mary occupying the visual center;
- state and relationship cards visible without opening a debug screen;
- menu navigation that feels like a game/character UI instead of a website;
- persistent chat at the bottom;
- animation/state changes rather than full page reloads.

The target image is not shipped as the functioning UI. The application reproduces it with actual panels, buttons, Three.js/VRM rendering, Qt signals, and live Mary state.

## Main application layout

```text
┌────────────────┬─────────────────────────────────────┬─────────────────┐
│ Mary           │ custom title/status bar             │ Memory          │
│ AI Companion   ├─────────────────────────────────────┤ Highlights      │
│                │                                     │                 │
│ Chat           │            LIVE VRM MARY            │ Continuity      │
│ Memories       │                                     │                 │
│ Personality    │                                     │ Mood            │
│ Studio         │                                     │                 │
│ Gallery        │                                     │ Activities      │
│ Media          │                                     │                 │
│ Voice & Avatar │   translucent conversation overlay  │ Providers       │
│ Settings       ├─────────────────────────────────────┤                 │
│                │ message input · mic · send          │                 │
│ Live state     │ quick modes / command palette       │                 │
│ Music player   │                                     │                 │
└────────────────┴─────────────────────────────────────┴─────────────────┘
```

## What is real in 12.7

### Mary / chat
- canonical `MaryApplication` is the only Mary instance;
- typed conversation;
- cloud/local routing from the existing router;
- provider failure isolation;
- authoritative desktop conversation state;
- typed and microphone barge-in.

### VRM
- `MaryCosma.vrm` loaded locally;
- Three.js + `@pixiv/three-vrm`;
- geometry-based framing;
- full / portrait / close views;
- blink;
- idle vertical/head motion;
- emotion-expression mapping;
- real speech-waveform mouth movement during TTS playback.

### Voice
- existing opt-in TTS path preserved;
- existing Groq Whisper STT path preserved;
- UI reflects enabled/disabled provider state;
- text output remains authoritative when voice fails.

### Dashboard
- represented mood / intensity / arousal;
- memory counts;
- current source-aware creator-profile highlights;
- relationship continuity label and derived continuity index;
- recent relationship/milestone/decision activity;
- actual active curiosities;
- personality trait strengths;
- values/preferences;
- effective provider route and availability;
- current task / agency counts.

No API keys, prompt bodies, or arbitrary raw state files are put into the normal dashboard payload.

### Studio
The UI shape exists now:

```text
Unbeknownst
├── Book 1
│   ├── Chapter 01
│   ├── Chapter 02
│   ├── Chapter 03
│   ├── ...
├── Characters
├── Lore
├── Locations
├── Storyboards
└── References
```

The chapter entries are currently UI scaffolding. On the personal PC, bind them to the real private project directory rather than inventing manuscript data in the package.

### Creative external apps
The desktop has a finite registry for:

- Adobe Photoshop
- Clip Studio Paint
- Krita
- Blender
- DaVinci Resolve
- Audacity

The UI cannot execute arbitrary shell commands. Applications are discovered from explicit environment variables / selected common paths and only known registry keys can be launched.

### Media
- local audio picker/player works through the Qt bridge;
- persistent mini-player exists in the left rail;
- YouTube search can be explicitly opened in the normal browser;
- future Watch Together surface has a defined UI location.

### Launcher
`MaryLauncher` is separate from `MaryV2`.

Launcher 12.7 supports:

- PLAY MARY;
- installed version/channel display;
- optional HTTPS manifest check;
- semantic version comparison;
- SHA-256 verified update download;
- staging downloads outside Mary's `data/` tree.

It intentionally does **not** replace the running application automatically yet. Applying/rolling back version folders needs one Windows build/install validation first.

## Home-PC visual tuning checklist

The exact VRM and Qt/WebEngine result cannot be truthfully pixel-perfect-tested in this container. On the personal PC, compare the running app beside `desktop/design/MARY_UI_TARGET.png` and tune:

1. VRM scale and vertical position;
2. center-stage lighting;
3. chat-card width/height;
4. left/right rail width at the actual monitor resolution;
5. glow strength;
6. title/logo size;
7. panel density;
8. small-font readability;
9. window resize behavior;
10. animation smoothness on the target GPU.

The layout and style tokens live primarily in `desktop/src/style.css`; the visual tuning does not require backend redesign.

## Performance notes

The central VRM renderer caps pixel ratio at 2. If the old GPU struggles:

- cap at 1.25–1.5;
- reduce antialiasing;
- reduce the avatar canvas size before changing Ollama;
- keep UI animation at transform/opacity-only where practical.

Ollama inference and VRM rendering are separate bottlenecks. Do not downgrade the model solely because the UI frame rate is low; measure them independently.

## Next PC milestones

1. Build Vite successfully on Windows.
2. Launch `scripts\launch_launcher_windows.ps1`.
3. Press PLAY and confirm the main shell loads.
4. Confirm VRM framing / idle / blink.
5. Confirm typed Mary conversation.
6. Confirm actual mood/memory/provider panels update after a turn.
7. Configure TTS/STT and test barge-in.
8. Test a local music file.
9. Configure Photoshop/other app path if desired and test launch.
10. Bind Studio to the private Unbeknownst project structure.
11. Only after those pass, build `MaryLauncher.exe` + `MaryV2.exe`.
12. Then implement versioned install/apply/rollback.

## Future modes without fragmenting Mary

Every mode remains a view/tool surface over the same Mary:

```text
Companion / Chat
Studio / Unbeknownst
Art / Storyboards
Media / Watch Together
Gallery / References
Voice / Avatar
Settings / Runtime
```

No mode should instantiate a separate character, provider router, memory store, or relationship model.
