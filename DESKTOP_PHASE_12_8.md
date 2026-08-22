# MaryV2 12.8 Desktop — Ecosystem + Presence

12.8 is the first attempt to make Mary feel like a real game/companion application rather than a terminal runtime with an avatar attached.

## Visible application surfaces

- persistent Chat + live VRM center stage;
- Memories;
- Personality;
- Studio / Unbeknownst project editor;
- Study;
- Command Center;
- Focus With Mary;
- Stream & Presence status;
- Gallery;
- Media/local music;
- Voice & Avatar;
- Settings;
- command-palette-only workspaces: personal Search, Research Notebook, Mary Arcade, Runtime & Latency.

The right inspector remains live while Mary is open and exposes grounded mood, continuity, current curiosity, memory/activity, ecosystem counts, and actual provider route state.

## Visual language

The UI is intentionally game-like: frameless window, boot sequence, dark glass/HUD panels, neon pink/purple/cyan accents, holographic stage rings, animated glow, local hover/select/startup sounds, and a persistent character stage. The visual targets are:

- `desktop/design/MARY_UI_TARGET.png`
- `desktop/design/MARY_12_8_ECOSYSTEM_TARGET.png`
- `desktop/design/MARY_12_8_PROMO_TARGET.png`

The targets are art direction, not fake runtime screenshots.

## Local voice policy

`MARY_TTS_PROVIDER=local_first` chooses configured Piper first, then Windows SAPI on Windows. ElevenLabs remains optional premium fallback and is disabled as an automatic fallback unless `MARY_TTS_ALLOW_CLOUD_FALLBACK=true`.

Speech recognition can remain Groq for first boot. `faster-whisper` is an optional local install later.

## Presence policy

Presence is a typed context layer, not another chatbot. Environment events do not become creator/system instructions, and low-salience events may result in silence. Raw screenshot/frame material is stripped before Presence state can retain metadata.

Twitch/OBS/vision are represented as external skills but disabled by default until the local desktop is proven on the personal PC.
