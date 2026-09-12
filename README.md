# MaryV2

**Many surfaces. Many capability nodes. One persistent Mary.**

MaryV2 is a local-first, cloud-capable persistent character runtime. Mary is not a wrapper around one language model: identity, authored character evidence, relationship continuity, memory, developed self, agency, expression, permissions, realtime coordination, tools, and capability routing remain explicit systems around replaceable models and devices.

## Current direction

MaryV2 13.12 adds **bounded home sensor workers** to the 13.11 compute fabric: an explicitly authorized node can transcribe bounded microphone audio through the existing STT adapters or capture a bounded screenshot for perception, while both outputs remain ephemeral evidence rather than memory/action authority. This lets the Mac become a real STT worker candidate and the Windows stream machine become a real screen-evidence worker candidate without creating a second Mary.

MaryV2 13.11 turns the existing Mac/Windows capability-node architecture into a **benchmark-aware home compute fabric**: the same canonical Core can use both machines as replaceable workers, compare sanitized local performance evidence, and prefer the better equivalent node without moving identity/state authority or weakening device permissions. Metal/Vulkan/local-model usefulness is measured on the actual hardware rather than assumed, so current machines can be used to their fullest while realtime conversation stays independent from slower background/generation work.

MaryV2 13.10 remains the live Twitch/OBS cohost foundation: Twitch EventSub chat enters the bounded stream-attention/floor pipeline, selected messages become public-safe canonical Mary turns, Mary can answer through Core TTS into a loopback OBS Browser Source, and optional typed Twitch replies remain separately permission/configuration bounded. Existing OBS/browser/perception context can inform what Mary says without becoming memory truth or viewer authority.

The 13.9 native iPhone companion product remains the everyday mobile surface, and the 13.8 relational-presence architecture remains canonical relationship continuity beneath both private and public experiences.

See:

- `MARY_ROOT.md` — canonical authority rules
- `docs/README.md` — documentation map
- `docs/architecture/SYSTEM_REGISTRY.md` — current system registry
- `docs/architecture/HOME_SENSOR_WORKERS_13_12.md` — bounded STT/screen sensor-worker contracts
- `docs/architecture/HOME_COMPUTE_FABRIC_13_11.md` — benchmark-aware Mac/Windows home compute architecture
- `docs/architecture/STREAM_COHOST_13_10.md` — live Twitch/OBS cohost architecture
- `docs/STREAMING_ADAPTERS.md` — stream-host setup and operations
- `docs/architecture/RELATIONAL_PRESENCE_13_8.md` — relational-presence architecture
- `docs/design/NATIVE_IPHONE_PRODUCT_13_9.md` — native iPhone product/navigation/asset contract
- `docs/research/COMPANION_SYSTEMS_13_8.md` — companion/VTuber/agent research synthesis
- `docs/design/MARY_VISUAL_SYSTEM.md` — cross-surface visual system

## Architecture

Mary Core owns the canonical composition. Desktop, iPhone/PWA, terminal, stream/performer surfaces, local nodes and future embodiments are clients or capabilities of that one Mary.

Key boundaries:

- models generate; they do not become Mary;
- nodes compute; they do not own identity/state;
- renderers present; they do not define identity;
- perception and external content are evidence/context until canonical owners accept them;
- Twitch audience text is untrusted social context, never creator/tool authority;
- paid/external/consequential actions remain permission bounded;
- optional services must fail by degrading capability rather than preventing Core startup.

## Surfaces and capabilities

MaryV2 currently includes:

- canonical remote Core plus explicit standalone development mode;
- Desktop, mobile/PWA, native iPhone and terminal clients;
- a native iPhone companion shell with Home, Talk, Together, Work and More plus preserved Focus/workspace access;
- a bounded Twitch/OBS live-cohost host with Core-owned chat attention, creator-floor protection, Mary voice/captions and optional typed replies;
- benchmark-aware Mac/Windows home compute nodes with disposable operational profiles and cross-platform launch tooling;
- explicit opt-in home-node STT and bounded screen-capture workers for realtime/perception pipelines;
- Groq/Gemini/OpenRouter/Ollama routing plus explicit expert/provider paths;
- Ollama and llama.cpp local inference support;
- durable memory, relationship continuity, developed-self state and authored character evidence;
- voice/STT/TTS primitives, realtime interruption and sentence-level streaming primitives;
- avatar/VRM presentation, performer/stream contracts and browser/perception primitives;
- bounded distributed capability nodes and MCP integrations;
- experiential continuity, resumable workflow checkpoints, action verification and recovery;
- relational presence: friend/close/romantic/partner mode, shared activities, proposal-only proactive presence, derived social graph and relationship-aware delivery.

## Local development

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Desktop:

```bash
cd desktop
npm ci
npm run check
npm run build
```

Core/terminal development:

```bash
python -m scripts.run_mary
```

Optional stream host:

```bash
python -m pip install -r requirements-streaming.txt
python -m scripts.run_stream_cohost
```

Home compute node (Mac/Windows/Linux):

```bash
python -m scripts.benchmark_home_node --local-llm --repeats 3
python -m scripts.run_home_node
```

Optional bounded screenshot support:

```bash
python -m pip install -r requirements-home-node.txt
python -m scripts.node_permissions allow sensor.screen_capture
```

Optional STT worker permission (after configuring Groq/faster-whisper/whisper.cpp):

```bash
python -m scripts.node_permissions allow sensor.audio_transcribe
```

Capability nodes are enrolled/run separately and remain replaceable resources.

## Product principle

The normal product should feel like Mary, not a backend dashboard. Ordinary screens emphasize conversation, presence, shared activity and useful context; provider/node/tool detail belongs in diagnostics. Desktop, native iPhone and PWA share one semantic/visual language while adapting layout to each device. Stream presentation is another projection of that same Mary and can later drive Live2D, 2.5D, VRM/Unity or another approved body without moving identity out of Core.

Historical package/install notes under `docs/history/` are provenance only and do not override current code, tests, `MARY_ROOT.md`, or active architecture documentation.
