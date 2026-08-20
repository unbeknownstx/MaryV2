# MaryV2 Desktop

The desktop is the presentation layer for the canonical persistent `MaryApplication`.
It does not create a second identity, memory store, relationship model, or provider router.

## Setup / rebuild on Windows

```powershell
python -m pip install -r requirements-desktop.txt
cd desktop
npm ci
npm run build
cd ..
```

Mary's VRM remains at:

```text
desktop/public/models/MaryCosma.vrm
```

Rebuild after changing the frontend or VRM.

## Launch

```powershell
python -m scripts.run_desktop
```

## Live character state

The Qt bridge publishes a display-safe runtime snapshot to the frontend. The UI can show:

- continuity/persistence capability
- relationship familiarity label
- represented mood/intensity and energy
- bounded memory count
- idle/listening/transcribing/thinking/speaking/interrupted status
- current task
- provider/resource status
- privacy/paid-expert policy

This surface intentionally does not expose raw memories, prompts, API keys, or private internal payloads.

## Failure isolation

Text conversation remains authoritative. Voice, avatar presentation, microphone input, or an individual provider may fail without being allowed to swallow Mary's text response or corrupt persistent state.
