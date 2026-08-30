# MaryV2 Mobile Companion — 12.12.2 Mobile Surface

This package adds an installable phone/browser surface **without forking Mary's identity or rewriting the canonical runtime**.

## What it reuses

- `MaryApplication` and the canonical pipeline
- durable memory / developed-self / relationship state
- provider routing and host-capability detection
- Mary dashboard/live-character state
- ecosystem workspaces (Command, Focus, Study, Research)
- the existing desktop Vite UI, Three.js renderer, and `MaryCosma.vrm` when `desktop/dist` is available
- a bundled zero-build phone shell using the same desktop visual language when Vite has not been built

The phone is a client. It does not own a second Mary.

## Fastest Replit/mobile path

1. Copy this package into the Replit project.
2. Keep your existing Replit Secrets / `.env` provider keys. Do **not** put API keys in browser JavaScript.
3. Run:

   ```bash
   python -m scripts.run_mobile
   ```

   No Node/Vite install is required for the included standalone mobile shell. If you later run `cd desktop && npm ci && npm run build`, Mary automatically prefers the richer shared Desktop build when `desktop/dist` exists.

4. Replit exposes the web port. Open it on the iPhone.
5. On a non-loopback host Mary protects the API with a bearer token. If `MARY_MOBILE_TOKEN` is not set, the server generates one and prints it in the console. Enter it once when the mobile UI asks; the browser stores it locally.
6. In Safari choose **Share → Add to Home Screen**. Mary then opens as a standalone PWA.

The package includes a no-build standalone mobile shell, so normal mobile use does not depend on npm. The shared Desktop Vite path remains available as an optional richer frontend when built on your PC/Replit.

## Windows / home-PC mode

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_mobile
```

By default local development binds only to `127.0.0.1`. To allow another device on your LAN, set `MARY_MOBILE_HOST=0.0.0.0`; a mobile access token will then be required/generated. For access away from home, put this behind a private HTTPS tunnel/VPN rather than exposing the port directly to the public internet.

## Mobile behavior

- typed chat runs the same canonical Mary pipeline
- the zero-build mobile shell uses Mary's bundled reference art for a lightweight character stage
- when `desktop/dist` is built, the same HTTP bridge can serve the richer shared desktop frontend, including the existing Three.js/VRM path
- browser/device speech synthesis provides a free voice output path
- browser speech recognition is used for push-to-talk when the browser exposes it; typing always remains available
- Home, Chat, Memory, Focus, and System are pinned to the zero-build mobile bottom navigation
- when the shared desktop Vite frontend is built, its wider workspace set remains available through the responsive desktop UI
- desktop-only file pickers/app launch actions are intentionally not exposed through the remote transport

## Environment options

- `MARY_MOBILE_HOST` — bind host; Replit defaults to `0.0.0.0`, local development to `127.0.0.1`
- `MARY_MOBILE_PORT` — port; otherwise `PORT` or `8080`
- `MARY_MOBILE_TOKEN` — optional explicit bearer token
- `MARY_MOBILE_STATIC_ROOT` — optional custom built UI path

## Security boundary

Provider API keys remain server-side. The mobile client receives only bounded display/runtime state and the Mary responses it requested. Non-loopback access is token protected by default.

---

## 12.13 Mobile Voice Upgrade

The mobile surface now supports server-side Mary TTS and server-side microphone
transcription with device/browser fallbacks. See `MOBILE_12_13_VOICE_SETUP.md`.

Quick readiness check:

```bash
python -m scripts.check_mobile_voice
```

Token rotation:

```bash
python -m scripts.rotate_mobile_token
```
