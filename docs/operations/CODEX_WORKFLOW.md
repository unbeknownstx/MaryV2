# MaryV2 + Codex in VS Code

Open `C:\Users\Melvin\Documents\GitHub\MaryV2` as the VS Code workspace. Codex should read `AGENTS.md`, `CURRENT_STATE.md`, and `DEVELOPMENT_PLAN.md` before changing code.

Safe working order:
1. Inspect the existing owner/module before editing it.
2. Do not read or expose `.env` values and do not use live persistent `data/` in tests.
3. Make the smallest coherent architecture change that preserves existing owners/boundaries.
4. Run **Mary: Fast Check**.
5. Run focused live tests only when the creator explicitly wants provider/TTS/model calls.
6. Run **Mary: Full Tests** for broad source validation.
7. Run **Mary: Release Gate** before calling a release ready.
8. Use GitHub Desktop for commit/push on the canonical Windows host.

Useful explicit labs:
- **Mary: Local Model Lab** benchmarks already-installed Ollama models and writes a report under `runtime_reports/`.
- `scripts\pull_local_model_candidates.ps1` installs the small comparison tier only when explicitly run.
- `scripts\run_voice_lab_windows.ps1` is offline by default. `-Synthesize` intentionally makes ElevenLabs TTS calls.

Codex should treat language models as Mary capabilities, not Mary's identity. The local mind/reservoir, canonical state, relationship, personality, expression and governance boundaries remain authoritative.
