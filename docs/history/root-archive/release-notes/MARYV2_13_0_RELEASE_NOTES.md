# MaryV2 13.0 Release Notes

## Core evolution

- Added persistent intentional-conversation modes: Adaptive, Talk/Engaged and Deep.
- Preserved fast routing for ordinary social turns while giving intentional threads larger reasoning/output budgets.
- Added grounded conversational initiative using real relationship-curiosity state.
- Expanded natural learning invitations such as “ask me questions” and “get to know me.”
- Added post-turn ExperienceJournal + GrowthEngine.
- Enabled safe automatic semantic consolidation on meaningful turns.
- Added strict evidence-based automatic promotion for mature preference candidates.
- Added grounded development/shared-achievement milestones.
- Added 13.0 system doctor and terminal conversation/growth commands.
- Added a display-safe environment parity exporter/comparator to catch Windows/Replit/macOS configuration drift without exposing secrets.
- Extended diagnostics to explicitly verify Conversation Engagement and Growth Engine wiring.

## Voice

- Reset ElevenLabs defaults to a neutral natural baseline.
- Dynamic delivery/emotion shaping is off by default and explicitly opt-in.
- Added private server-side Voice Lab profiles and Mobile controls.
- Retained TLS compatibility hotfix and iOS asynchronous audio-unlock/playback path.

## Routing

- Retained 12.13.2 provider-specific configuration fixes.
- Fast Groq conversation fallback now uses `openai/gpt-oss-20b` instead of the unavailable Llama route.
- Existing live route diagnostic retained for provider-level error truth.

## Mobile

- Protocol 3.
- Added AUTO/TALK/DEEP mode strip.
- Added Growth workspace and development status on Home/Memories/Runtime.
- Personality presentation now separates values, likes/interests, dislikes/aversions and developing preferences.
- Voice & Avatar now includes Voice Lab.
- Service-worker cache bumped to force 13.0 frontend refresh.

## Desktop

- Added Growth workspace to launcher/navigation.
- Dashboard now exposes engagement/growth state.
- Existing VRM, voice, lip sync, workspace ecosystem and presence architecture remain intact.

## Compatibility and privacy

- No `.env`, `data/`, API keys, mobile token, personal memories or relationship state are shipped in the release archive.
- Existing 12.x milestone verifiers were updated so the 13.0 release can prove those foundations remain installed.
- One canonical Mary runtime/state remains the design contract.
