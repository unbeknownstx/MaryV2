# MaryV2 13.0 Migration / Paste-Over Guide

13.0 is designed as a **paste-over evolution** of the current MaryV2 project. It does not create a second Mary and it does not ship private runtime state.

## Before overlaying

Commit or back up the current repository. Keep these local/private items exactly where they are:

- `.env` / Replit Secrets
- `data/` (memory, relationship, developed self, goals, runtime state)
- local `.venv` / virtual environment
- any private creative workspace outside the repo

The 13.0 release archives intentionally exclude those paths.

## GitHub / Windows

1. Extract `MaryV2_13_0_FULL_EVOLUTION_OVERLAY.zip` over the project root.
2. Let matching source/frontend files replace the older versions.
3. Do **not** delete `data/` or `.env`.
4. Commit/push with GitHub Desktop.
5. Run:

```powershell
python -m scripts.check_mary_13
python -m pytest tests -q
python -m scripts.run_release_verification
```

For the desktop frontend on a normal internet-connected development machine:

```powershell
cd desktop
npm ci
npm run check
npm run build
cd ..
```

## Replit

Pull the same GitHub commit, keep existing Secrets, then run:

```bash
python -m scripts.check_mary_13
python -m scripts.check_llm_routes --live
python -m scripts.check_mobile_voice
python -m scripts.run_mobile
```

If the PWA shows an older UI, fully close/reopen it or refresh once; 13.0 bumps the service-worker cache.

## Known-good Replit conversation model

```text
MARY_LLM_MODEL=openai/gpt-oss-20b
MARY_GROQ_MODEL=openai/gpt-oss-20b
```

Provider-specific model variables are authoritative in 13.0.

## New controls

Terminal:

```text
/talk
/deep
/auto
/conversation
/growth
```

Mobile Chat: `AUTO / TALK / DEEP`

Mobile Workspaces: `Growth`, improved `Personality`, and `Voice & Avatar → Voice Lab`.

## Cross-host drift check

13.0 adds a display-safe configuration profile tool. It never exports API keys or private memory.

Export on one host:

```bash
python -m scripts.check_environment_parity --export mary-config.json
```

Copy that small JSON to another host and compare:

```bash
python -m scripts.check_environment_parity --compare mary-config.json
```

This is intended to catch the kind of silent Windows/Replit model/config drift that can otherwise make identical source behave differently.
