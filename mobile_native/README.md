# Mary.app — Native iPhone shell

This folder is a dependency-free Xcode project for the MaryV2 mobile client.
It bundles the same `mobile_web` UI and adds native iOS speech recognition,
AVSpeechSynthesizer voice output, haptics, safe-area/status-bar integration,
and persistent on-device server/token settings.

## Build on your Mac

1. Start MaryV2 somewhere reachable by the phone:
   `python -m scripts.run_mobile`
2. Open `mobile_native/MaryMobile.xcodeproj` in Xcode.
3. Select the `MaryMobile` target → Signing & Capabilities → choose your Personal Team.
4. Connect/unlock your iPhone and select it as the run destination.
5. Press Run.
6. On first launch Mary asks for the Mary server URL and mobile access token.

No App Store submission is required for a personal install. A free Apple
Personal Team works for device testing, but free provisioning expires and the
app must periodically be re-signed from Xcode.

## Connection examples

- Hosted/Replit: `https://<your deployment host>`
- Home LAN while on the same Wi-Fi: `http://192.168.x.x:8080`
- Secure tunnel/VPN: use the HTTPS address provided by your tunnel.

The app never embeds Groq, Gemini, OpenRouter, OpenAI, ElevenLabs, or other
provider secrets. Those remain in MaryV2's host `.env`.

## Keep the embedded web bundle synchronized

`mobile_web/` is the canonical source. Before opening Xcode after web/PWA work:

```bash
python -m scripts.sync_mobile_web --check
python -m scripts.sync_mobile_web --sync
```

or double-click `SYNC_WEB_FROM_PROJECT.command` on macOS. The repository tests also verify that `MaryMobile/www` is an exact generated copy.

MaryV2 13.2 conversation IDs and Core/device-node status are client features; the iPhone app still owns presentation and local iOS speech/haptics only, never Mary identity or canonical memory.
