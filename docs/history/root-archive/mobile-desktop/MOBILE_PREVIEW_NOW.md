# Mary Mobile — Preview on iPhone Now

This patch adds the dedicated phone-first Mary interface to the existing MaryV2 project. It does **not** create another Mary. The browser UI talks to the same `MaryApplication`, state, memory, relationship, cognition, and provider router that the host project already uses.

## Replit — fastest path from iPhone

1. Back up or commit the current Replit project if desired.
2. Upload `MaryV2_12_12_2_MOBILE_PHONE_FRONTEND_PATCH.zip` to the project.
3. Extract/copy the archive **over the MaryV2 project root**.
   - Keep your current `.env` / Replit Secrets.
   - Keep your current `data/` directory.
   - Do not replace private persistent state with a clean copy.
4. Run the Replit workflow **Mary Mobile**, or run:

   ```bash
   python -m scripts.run_mobile
   ```

5. Open the web URL Replit exposes.
6. On a public host Mary requires a mobile access token. If `MARY_MOBILE_TOKEN` is not already set, the terminal prints a `FIRST-RUN MOBILE ACCESS TOKEN`. Copy it into the connection sheet once.
7. In iPhone Safari: **Share → Add to Home Screen**.

The dedicated `mobile_web/` UI is now preferred even if `desktop/dist/` exists, so this command will not accidentally reopen the desktop layout.

## What the phone UI contains

- Mary portrait/live state stage with a still-art fallback when the desktop VRM is unavailable
- Chat through the canonical MaryV2 pipeline
- Home / mood / relationship / memories / provider state
- Command Center
- Focus
- Memories
- Personality
- Cognitive reservoir / Mind
- Studio text workspace
- Study
- Presence
- Personal Search
- Research
- Arcade
- Gallery
- Media
- Voice & Avatar
- Runtime
- Settings
- PWA home-screen installation

## Free-hosting model

For the immediate preview, Replit can serve **both** the frontend and Mary backend from one URL. That avoids CORS/configuration work and is the simplest phone-only path. The frontend can later be split onto a free static host without changing Mary’s architecture.
