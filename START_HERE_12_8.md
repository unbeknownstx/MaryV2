# MaryV2 12.8 — Start Here on the Windows PC

MaryV2 12.8 already contains the validated 12.7 desktop/game-shell baseline. **Do not install 12.7 first and then overwrite it again.** Use 12.8 as one consolidated migration, while keeping your current folder as the rollback copy.

## 0. Protect the current Mary

Before copying new source, back up these separately:

- the entire current MaryV2 project folder;
- `.env`;
- `data/`;
- any avatar/model source assets not already copied elsewhere.

Do not delete the old working folder until 12.8 is live on the PC.

## 1. GitHub Desktop

1. Open the current MaryV2 repository in GitHub Desktop.
2. **Fetch origin** and **Pull origin**.
3. Make a copy of that freshly pulled repository folder, or create a `12.8-integration` branch.
4. Work only in that copy/branch.

## 2. Overlay this 12.8 source

Extract the 12.8 PC Full ZIP to a staging folder first. Copy its project contents into the integration copy.

Never overwrite intentionally:

- `.git/`
- your real `.env`
- your real `data/`
- `.venv/`

The release ZIP intentionally contains no `.env` and no `data/`.

## Fast path (recommended after you have backed up `.env` and `data/`)

12.8 includes a conservative first-boot helper:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\first_boot_windows.ps1
```

It creates/reuses `.venv`, installs Python dependencies, runs doctor/routes, runs the complete tests and offline release gate, then builds the frontend if Node/npm are available. It does not delete or replace `.env` or `data/`. If anything fails, stop at that stage and paste the output into ChatGPT.

## 3. Python environment

From PowerShell in MaryV2:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# If your old venv is healthy:
.\.venv\Scripts\Activate.ps1

# Otherwise create a clean one:
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt
```

## 4. First diagnostic

```powershell
python -m scripts.doctor
```

Stop and paste the output into ChatGPT if anything important is red. Node/npm warnings can wait until the Python baseline is green.

## 5. Provider/Ollama check

```powershell
ollama --version
ollama list
python -m scripts.check_llm_routes
```

Do **not** change the Ollama model yet. First measure actual latency on the PC.

## 6. Prove the source baseline

```powershell
python -m pytest -q
python -m scripts.run_release_verification --offline
```

12.8 reference result at package freeze:

- 660 passed
- 1 intentionally skipped live-provider test
- diagnostics 54/54 PASS
- complete deterministic/offline release gate PASS

If there is a failure on your PC, stop there and paste the failure output before doing frontend work.

## 7. Run Mary without the frontend

```powershell
python -m scripts.run_mary
```

Try normal conversation plus:

```text
/state
/route
/memory-status
/environment
```

This proves identity/memory/provider state before adding rendering and microphones.

## 8. Frontend dependencies

Check:

```powershell
node --version
npm --version
```

Then:

```powershell
cd desktop
npm ci
npm run check
npm run build
cd ..
```

The build environment used to assemble this ZIP could run the JavaScript syntax checks, but its npm registry connection timed out before Vite could be downloaded. The real host-native Vite build therefore happens on your PC.

## 9. Launch the desktop

```powershell
.\scripts\launch_windows.ps1
```

Or launch the game launcher:

```powershell
.\scripts\launch_launcher_windows.ps1
```

The first goal is simple: Mary opens, the real VRM renders, chat works, and live state appears around her.

## 10. Local voice after the first GUI launch

12.8 ships local-first voice support. Windows SAPI needs no extra dependency. Optional local Whisper can be installed later:

```powershell
.\scripts\setup_local_voice_windows.ps1
# or
.\scripts\setup_local_voice_windows.ps1 -InstallWhisper
```

Recommended `.env` policy:

```dotenv
MARY_TTS_PROVIDER=local_first
MARY_TTS_ALLOW_CLOUD_FALLBACK=false
MARY_STT_PROVIDER=groq
```

Once basic voice works we can benchmark Piper and faster-whisper instead of spending ElevenLabs credits on ordinary conversation.

## 11. Only after the live desktop is stable

Then enable and troubleshoot, in this order:

1. UI visual tuning against `desktop/design/MARY_UI_TARGET.png` and `MARY_12_8_ECOSYSTEM_TARGET.png`.
2. VRM framing, FPS, expressions, idle animations.
3. Local TTS/STT and measured latency.
4. Study / Command Center / Focus / personal search.
5. Presence initiative and pending thoughts.
6. External integrations last: Twitch, OBS, visual context, Ren'Py, Photoshop/Blender bridges.

That keeps external services from hiding a basic desktop/runtime problem.
