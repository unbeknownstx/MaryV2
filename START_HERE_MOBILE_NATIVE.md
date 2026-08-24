# MaryV2 12.12.2 — Native Mobile Companion

This release keeps one canonical MaryV2 runtime and adds two mobile clients:

1. `mobile_web/` — zero-build browser/PWA client.
2. `mobile_native/` — dependency-free native iPhone Xcode project (`Mary.app`).

Mary Mobile does not fork identity, memory, relationship state, personality,
cognition, agency, provider routing, or ecosystem state. Those remain owned by
the same `MaryApplication` running on the MaryV2 host.

## What now works on mobile

- Chat through the canonical Mary pipeline
- Home / companion pulse
- Command Center add/update
- Focus start/stop
- Memories / continuity
- Personality / values / preferences / agency
- Local Mind status + reservoir rebuild
- Studio read/edit/save inside the configured sandboxed creative workspace
- Study project creation + due-card visibility
- Presence / Mary Inbox / pending thoughts / integration status
- Personal Search
- Research thread creation
- Arcade surface
- Gallery / Mary art + project image references
- YouTube metadata search + save-to-Research
- Voice & Avatar controls
- Runtime/provider/latency diagnostics
- Connection/settings

The native iPhone shell additionally provides:

- Native speech recognition (`Speech` framework)
- Native voice output (`AVSpeechSynthesizer`)
- Native haptics
- iPhone app icon + launch screen
- Persistent Mary server/token settings
- Local-network access support

## Run Mary's mobile server

### Replit/Linux/macOS

```bash
python -m scripts.run_mobile
```

### Windows

```powershell
.\.venv\Scripts\python.exe -m scripts.run_mobile
```

For another device on the same LAN, set:

```text
MARY_MOBILE_HOST=0.0.0.0
```

Non-loopback hosting requires a bearer token. If `MARY_MOBILE_TOKEN` is not
configured, Mary creates one under `data/mobile/access_token.txt` and prints it
once on first launch.

## Install Mary.app on iPhone

1. Copy/open this project on a Mac with Xcode.
2. Open `mobile_native/MaryMobile.xcodeproj`.
3. Select the `MaryMobile` target → **Signing & Capabilities**.
4. Choose your Apple **Personal Team**.
5. Connect/unlock the iPhone and choose it as the run destination.
6. Press **Run**.
7. On first launch enter the URL of the Mary mobile server and its mobile token.

The Xcode project has no CocoaPods, Swift Package Manager, Capacitor, React
Native, Expo, or npm dependency. The UI is bundled directly into the app.

## Browser/PWA fallback

Open the Mary mobile server in Safari and use **Share → Add to Home Screen**.
The same UI runs as a PWA when the native app is not installed.

## Security boundary

- Provider API keys stay server-side.
- Mobile API access is token-protected on non-loopback hosts.
- Native/file-origin CORS is allowed only for the native client origin plus
  explicitly configured `MARY_MOBILE_ALLOWED_ORIGINS`.
- Studio remains confined to `MARY_CREATIVE_WORKSPACE` and rejects path escape.
- Windows app launching, Explorer/Finder opening, and arbitrary host file
  pickers are not exposed remotely.
