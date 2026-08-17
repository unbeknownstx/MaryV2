# MaryV2 Desktop Alpha

This is a presentation layer over the existing MaryV2 Python runtime.

## First-time setup

From the MaryV2 repository root:

```powershell
pip install -r requirements-desktop.txt
cd desktop
npm install
npm run build
cd ..
```

Put Mary's VRM at:

```text
desktop/public/models/MaryCosma.vrm
```

If you add or replace the VRM after building, run `npm run build` again.

## Launch

```powershell
python -m scripts.run_desktop
```

## Architecture

```text
Qt window
  -> QWebEngineView
     -> Three.js + three-vrm
     -> QWebChannel
        -> MaryDesktopBridge
           -> canonical MaryApplication
              -> existing MaryV2 pipeline
```

The desktop layer does not own Mary's memory, identity, relationship model,
agency, tools, or LLM routing.
