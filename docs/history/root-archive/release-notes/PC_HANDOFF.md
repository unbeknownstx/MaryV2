> **For the fastest current Windows migration, follow `START_HERE_12_8.md` first.** This longer handoff remains the detailed migration/reference guide.

# MaryV2 12.8 — Personal PC / Ecosystem Handoff

This package includes the stable V2 core, the validated 12.7 game-style desktop/launcher baseline, and the 12.8 ecosystem/presence/local-voice pass. The personal PC is now where we validate the real VRM rendering, Vite build, TTS/STT devices, Ollama latency, visual tuning, and final executable packaging. The source package deliberately excludes `.env`, Python/Node environments, caches, and normal runtime `data/` state. Mary's private state should be backed up separately and restored deliberately.

## 1. On Replit before leaving it

From the MaryV2 repository root:

```bash
python -m scripts.verify_state_integrity
python -m scripts.backup_state
python -m scripts.run_release_verification --offline
```

`backup_state` creates a private `MaryV2-state-YYYYMMDD-HHMMSSZ.zip` beside the configured data directory in a `backups/` folder. It contains `data/` only. It does **not** contain `.env` or provider secrets.

Download both:

1. the final MaryV2 project package;
2. the newest `MaryV2-state-*.zip` if you want to carry Mary's current memories/relationship/agency state to the PC.

Keep your actual provider keys separately. Do not put them in GitHub or the state backup.

## 2. Put the project on the personal Windows PC

Recommended location:

```text
C:\Users\<you>\Documents\GitHub\MaryV2
```

Do not copy an old `.venv`, `node_modules`, `build`, or `dist` directory from another operating system. The setup script rebuilds host-native dependencies.

## 3. Install host prerequisites

Install these normally on the personal PC if they are not already present:

- 64-bit Python 3.11+
- Node.js 22.12+ with npm (Vite 8 also supports Node 20.19+)
- Ollama, if you want Mary's preferred private/local conversation route

The MaryV2 setup scripts do not require administrator-level system modifications themselves.

## 4. Create the Python environment and frontend dependencies

Open PowerShell in the MaryV2 directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

The setup script:

- creates `.venv` if missing;
- installs core + desktop Python dependencies;
- preserves an existing `.env`;
- creates `.env` from `.env.example` only when no `.env` exists;
- runs `npm ci` and builds the current desktop shell;
- runs the final build preflight;
- runs the deterministic offline release gate;
- checks persistent-state integrity.

## 5. Configure provider secrets

Edit the local `.env` only. Never put real keys into `.env.example` or `example.env.example`.

Normal V2 policy:

```text
character conversation: Ollama -> Groq -> Gemini -> OpenRouter
task/general free_first: Groq -> Gemini -> OpenRouter -> Ollama
private/offline: Ollama only
paid expert: OpenAI only when explicitly authorized for a task
```

OpenAI is optional for normal operation.

## 6. Install/check the preferred local Ollama model

Example:

```powershell
ollama --version
ollama pull qwen3:4b-instruct
```

Then run the strict local/runtime preflight:

```powershell
.venv\Scripts\python.exe -m scripts.final_preflight --build-ready --runtime-ready --strict-local --data-dir (Join-Path $env:LOCALAPPDATA "MaryV2\data")
```

This reports configuration presence and local Ollama status without printing provider-key values.

## 7. Restore Mary's private state before the first normal launch

First validate the state archive without writing anything:

```powershell
.venv\Scripts\python.exe -m scripts.restore_state C:\path\to\MaryV2-state-YYYYMMDD-HHMMSSZ.zip
```

On Windows, use the same canonical data directory that the future frozen EXE uses:

```powershell
$MaryData = Join-Path $env:LOCALAPPDATA "MaryV2\data"
.venv\Scripts\python.exe -m scripts.restore_state C:\path\to\MaryV2-state-YYYYMMDD-HHMMSSZ.zip --data-dir $MaryData
```

If validation passes, restore it:

```powershell
.venv\Scripts\python.exe -m scripts.restore_state C:\path\to\MaryV2-state-YYYYMMDD-HHMMSSZ.zip --data-dir $MaryData --apply
```

Restore refuses to overwrite a non-empty target data directory. That is intentional. If Mary has already created new PC state, back it up/move it first rather than silently merging two authoritative state trees.

Verify after restore:

```powershell
.venv\Scripts\python.exe -m scripts.verify_state_integrity --data-dir $MaryData
```

## 8. Verify routes and core runtime

```powershell
.venv\Scripts\python.exe -m scripts.doctor
.venv\Scripts\python.exe -m scripts.check_llm_routes
.venv\Scripts\python.exe -m scripts.run_release_verification --offline
```

Then run Mary in the terminal through the Windows canonical-state launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_mary_windows.ps1
```

That launcher points source-development Mary at `%LOCALAPPDATA%\MaryV2\data`, the same default state tree the frozen EXE will use. This avoids creating one relationship/memory history in the repo and another in the packaged app.

Recommended live acceptance prompts:

```text
hey mary, how do you feel about where we are with the project?
what do you remember we've been working on together?
what are you currently curious about?
i think we may have overcomplicated parts of your architecture. what do you think?
you don't have to agree with me. what do you actually disagree with?
```

Check `/route`, `/environment`, `/state`, `/last`, and `/memory-status` as needed.

## 9. Build and run the game-style frontend from source

The setup script already runs `npm ci` + `npm run build`. First launch the game-style launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_launcher_windows.ps1
```

Press **PLAY MARY**. During debugging you can bypass the launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1
```

Compare the actual UI beside `desktop\design\MARY_UI_TARGET.png`. Check VRM position, panel scaling, glow, small text, and frame rate on the real display/GPU.

Also verify:

- Chat sends a real Mary turn.
- Mood/energy panels update from Mary's emotion state.
- Memory highlights contain represented creator facts/preferences rather than demo text.
- Provider chips match `/route`.
- `Ctrl+K` opens the command palette.
- Local music selection plays.
- Voice/mic status reflects the configured TTS/STT state.
- Studio opens without creating a second Mary.

## 10. Optional creative-app configuration

Add only the tools you use to the private `.env`, for example:

```text
MARY_PHOTOSHOP_PATH=C:\Program Files\Adobe\Adobe Photoshop 2026\Photoshop.exe
MARY_BLENDER_PATH=C:\Program Files\Blender Foundation\Blender 4.5\blender.exe
```

The bridge uses a fixed application allowlist; the frontend cannot send arbitrary shell commands.

## 11. Bind Studio to the actual Unbeknownst project

The Studio layout is already present, but the chapter list is intentionally scaffolding until the private project directory is available. We will point `MARY_WORKSPACE_ROOT` at the correct private workspace and connect chapters/lore/storyboards without copying the book into Mary source control.

## 12. Build the standalone Windows programs

Once the live runtime is green:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Expected executables:

```text
dist\MaryLauncher\MaryLauncher.exe
dist\MaryV2\MaryV2.exe
```

Normal use becomes `MaryLauncher.exe` → **PLAY MARY**.

For a normal frozen install, writable Mary state defaults to:

```text
%LOCALAPPDATA%\MaryV2\data
```

and the default private packaged `.env` location is:

```text
%LOCALAPPDATA%\MaryV2\.env
```

`MARY_DATA_DIR` and `MARY_ENV_FILE` override those locations. `MARY_PORTABLE=1` intentionally keeps state beside the executable.

## 13. Before any risky future change

Create a state backup first:

```powershell
.venv\Scripts\python.exe -m scripts.backup_state
```

GitHub remains source history. Mary's live private state and provider credentials remain private local state.
