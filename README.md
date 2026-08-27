# MaryV2

MaryV2 is a private persistent character runtime for **Mary**. Mary existed as a character before this software; the runtime is the machinery that lets the same character converse, remember selectively, learn through controlled paths, use tools/models, speak through the desktop, survive restarts, and remain independent from any one LLM provider.

## Current consolidated baseline — 13.2 Unified Core

The current source line is **MaryV2 13.2 — Unified Core + distributed clients/capability nodes**. One long-lived Mary Core owns the canonical MaryApplication and durable character/workspace state. Desktop, Mac, Replit/PWA and mobile/native surfaces are clients; Windows/Mac can additionally advertise replaceable local capabilities such as PersonalSearch and Ollama without becoming identity owners.

13.2 also connects the previously separate internal paths more tightly: Ecosystem/Companion Pulse → TurnMind, Research → evaluated durable knowledge → reservoir retrieval, Agency priorities → cognition, bounded conversation IDs → real short-dialogue sessions, and TurnMind → cognition/reflection → expression/dialogue continuity. See `MARYV2_13_2_UNIFIED_CORE.md` and `MOBILE_REPLIT_13_2_CONVERGENCE.md`. Older `START_HERE_*` and release documents remain implementation history, not competing authorities.


## V2 invariants

- Mary is not the provider. Groq, Gemini, OpenRouter, Ollama, and optional paid OpenAI are replaceable capabilities.
- Persistent state is bounded. Persistence means continuity, not perfect recall or infinite storage.
- Active LLM context is selective and bounded; stored history is never dumped wholesale into prompts.
- Temporary task reasoning does not automatically become durable memory, relationship state, or developed self.
- Model output is advisory evidence. Tests, local state, authoritative sources, and explicit creator statements can outrank it.
- Paid OpenAI is excluded from `free_first` and requires explicit task-level authorization.
- Private/offline generation uses Ollama only.
- Tool capability and permission are separate. Consequential writes/actions remain approval-gated.
- Persistent JSON state is atomically replaced with a finite backup chain and recovery support.
- Every long-lived collection, task ledger, provider route, context path, and backup chain has a hard ceiling.

## Normal provider policy

```text
character conversation: configurable free route (current Windows profile: Groq -> Gemini -> OpenRouter -> Ollama)
task/general free_first: Groq -> Gemini -> OpenRouter -> Ollama
private/offline: Ollama only
paid expert: OpenAI (explicit task authorization only)
```

Ordinary personal/relational conversation has its own free-provider route. On the current Windows PC the recommended performance profile is cloud-first (`groq -> gemini -> openrouter -> ollama`) because the local 4B Ollama model is too slow for front-line conversation on the present hardware. Private/offline turns still force Ollama, and switching the conversation order back to Ollama-first remains a supported configuration choice. The authoritative TurnPolicyEngine still separates conversational generation from detached factual/technical/task work.

Breakthrough 11 adds process-local conversational supervision above that routing split: Mary can retain why she just asked a real relationship-curiosity question, temporarily suppress an interpretation the creator rejected, ground shared MaryV2 history and self-development questions in actual state, and revise semantic style loops or unsupported mind-reading locally without turning them into durable memory.

## First-time setup

MaryV2 now includes host-specific setup scripts that preserve an existing `.env` and rebuild frontend dependencies for the current machine instead of reusing another operating system's `node_modules`.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

macOS:

```bash
bash scripts/setup_macos.sh
```

For read-only prerequisite checks:

```text
python -m scripts.doctor
python -m scripts.final_preflight
```

The doctor/preflight report only configuration presence and host readiness; they never print provider-key values or modify Mary's persistent memory. The doctor may load the local `.env` into its own process so it can accurately report whether providers are configured.

## Run Mary in the terminal

From the repository root with the virtual environment active:

```powershell
python -m scripts.run_mary
```

On the personal Windows PC, prefer the canonical-state launcher so source Mary and the future frozen EXE share `%LOCALAPPDATA%\MaryV2\data`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_mary_windows.ps1
```

A developer convenience shim reaches the exact same runtime:

```powershell
python run_mary.py
```

Useful commands while Mary is running:

```text
/help       command help
/state      display-safe live character/runtime state
/resources  provider/token/paid-resource counters
/route      conversation/task route policy + last actual provider
/contract   display-safe architecture/authority contract
/last       last-turn provider, turn-policy, and reasoning metadata
/pending    approval-gated tool requests
/audit      read-only audit for obvious development/test creator-state residue
```

## Run Mary Desktop / Launcher

12.10 builds on the validated 12.9 runtime instrumentation and 12.8 ecosystem/presence shell. It adds Mary Home / Companion Pulse, typed cross-workspace Presence pathways, Focus-aware quiet behavior, local Portrait Art presentation beside the working VRM, stronger responsive polish, and Vite 8/Rolldown bundle-splitting configuration. The desktop remains a presentation layer over the same canonical `MaryApplication`; the Companion Pulse is read-only and does not become another memory or planner.

On Windows, normal source testing now starts with the launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_launcher_windows.ps1
```

Press **PLAY MARY** to open the main window. To bypass the launcher during debugging:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1
```

Direct Python development entry points also remain available:

```text
python -m scripts.run_launcher
python -m scripts.run_desktop
```

The approved visual reference is `desktop/design/MARY_UI_TARGET.png`. The implementation is a real local HTML/CSS/JS + Three.js/VRM interface, not a static screenshot. See `desktop/README.md`, `START_HERE_12_8.md`, `FINAL_PASS_12_8.md`, and the preserved visual targets under `desktop/design/`.

## Semantic memory promotion boundary

High importance makes an episodic memory eligible for review; it does **not** by itself make that episode semantic truth. Safe default promotion is limited to deterministic V2 semantic extraction (for example explicit likes/dislikes) and explicitly structured semantic facts. Generic important events, relationship/shared-work history, and obvious development probes remain in their authoritative stores instead of becoming `mary/remembers/...` semantic clutter. Legacy unstructured promotion remains available only through an explicit migration flag.

## Verify V2

The canonical no-spend release gate is:

```powershell
python -m scripts.run_release_verification --offline
```

This explicitly disables live LLM/OpenAI pytest flags in child processes. A normal test or release run must not spend paid OpenAI credits.

For the full local hard-test sequence:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\hard_test_v2.ps1
```

## Private state backup / migration

Before moving Mary between hosts or making a risky runtime change:

```text
python -m scripts.verify_state_integrity
python -m scripts.backup_state
```

Backups contain Mary's configured `data/` tree only and explicitly exclude `.env`/provider secrets. Restore is dry-run by default:

```text
python -m scripts.restore_state path/to/MaryV2-state-YYYYMMDD-HHMMSSZ.zip
python -m scripts.restore_state path/to/MaryV2-state-YYYYMMDD-HHMMSSZ.zip --apply
```

Restore refuses to overwrite a non-empty target state tree. See `PC_HANDOFF.md` for the complete Replit/macOS -> personal Windows PC sequence.

## Standalone desktop builds

After the hard-test gate is green, build on the operating system you intend to run. The build now produces **two applications**: the game-style launcher and Mary herself.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Expected outputs:

```text
dist\MaryLauncher\MaryLauncher.exe
dist\MaryV2\MaryV2.exe
```

macOS:

```bash
bash scripts/build_macos.sh
```

Frozen state is written outside replaceable application versions by default: `%LOCALAPPDATA%\MaryV2\data` on Windows and `~/Library/Application Support/MaryV2/data` on macOS. Set `MARY_PORTABLE=1` only when side-by-side state is deliberately desired. `MARY_DATA_DIR` and `MARY_ENV_FILE` always override the defaults.

The launcher can optionally check an HTTPS update manifest and SHA-256-verify/stage a newer ZIP. Automatic apply/rollback remains disabled until we validate the versioned installation flow on the personal PC.

See:

- `DESKTOP_PHASE_12_7.md`
- `PC_HANDOFF.md`
- `desktop/README.md`
- `docs/architecture/V2_FINAL_RUNTIME.md`

## Breakthrough 12 host portability

Mary's character/runtime core no longer assumes Ollama exists on every host. `RuntimeEnvironment` detects the current host and provider availability, while preserving separate preferred and effective routes. Use `/route` to inspect provider policy/effective routing and `/environment` to inspect display-safe host capabilities. Runtime questions are answered locally rather than being mistaken for web-search requests merely because they contain words such as `current` or `right now`.

### Windows first boot

The canonical Windows repository remains `C:\Users\Melvin\Documents\GitHub\MaryV2`. After preserving your existing private `.env` and runtime state, validate 12.10 with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\SETUP_WINDOWS_12_10.ps1
```

See `START_HERE_12_10.md` for the current canonical Windows setup, FAST/FULL/RELEASE test tiers, and 12.10 Presence/Presentation boundaries.


## 12.11 fast dialogue + connected presence

Mary now separates ordinary conversation from deliberate thinking. Short/social and ordinary conversational turns use a deterministic fast lane, a purpose-specific Groq conversation model (`MARY_GROQ_CONVERSATION_MODEL`, default `llama-3.1-8b-instant`), local character/style repair when safe, and ElevenLabs/local TTS independently. Semantic/provenance/capability boundary defects still retain the stronger revision path.

Optional integrations remain explicit and disabled by default: loopback read-only WebSocket presence (`MARY_WEBSOCKET_ENABLED`) and YouTube Data API public search (`MARY_YOUTUBE_ENABLED` + `YOUTUBE_API_KEY`). YouTube search metadata never becomes permanent Mary memory automatically; selected results can be explicitly saved into Research. Paid OpenAI remains the explicit expert route only.

## 12.12 Cognitive Reservoir + Character Runtime

12.12 adds a rebuildable local character-mind layer **above Mary's existing
canonical state and below language-model calls**.  Simple dialogue acts,
represented status and high-confidence local facts can be handled without an
LLM.  A bounded SQLite/FTS5 Cognitive Reservoir indexes provenance-bearing
projections of existing creator state, Mary preferences, semantic/episodic
memory and verified knowledge.  It is derived cache state, never a new identity
or truth authority.

The release also adds a hardware-conscious local Ollama model lab, optional
purpose-specific local conversation model routing, one deterministic
Expression Director shared by TTS and VRM presentation, and a character utility
layer for cheap idle/autonomy behavior where silence remains valid.

Start with `START_HERE_12_12.md`.  Useful development commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test_character.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test_full.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test_release.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_local_models_windows.ps1
```
