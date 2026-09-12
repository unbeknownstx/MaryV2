# MaryV2

**Many surfaces. Many capability nodes. One persistent Mary.**

MaryV2 is a local-first, cloud-capable persistent character runtime. Mary is not a wrapper around one language model: identity, authored character evidence, relationship continuity, memory, developed self, agency, expression, permissions, realtime coordination, tools, and capability routing remain explicit systems around replaceable models and devices.

## Current direction

MaryV2 13.8 is focused on **Relational Presence & Shared Life**: relationship continuity that can support close, romantic, or partner interaction without creating a second persona or second relationship database. Shared activities, proactive-presence proposals, social retrieval projections, and relationship-aware delivery build on the existing canonical Core.

See:

- `MARY_ROOT.md` — canonical authority rules
- `docs/README.md` — documentation map
- `docs/architecture/SYSTEM_REGISTRY.md` — current system registry
- `docs/architecture/RELATIONAL_PRESENCE_13_8.md` — 13.8 relational-presence architecture
- `docs/design/MARY_VISUAL_SYSTEM.md` — cross-surface visual system

## Architecture

Mary Core owns the canonical composition. Desktop, iPhone/PWA, terminal, stream/performer surfaces, local nodes and future embodiments are clients or capabilities of that one Mary.

Key boundaries:

- models generate; they do not become Mary;
- nodes compute; they do not own identity/state;
- renderers present; they do not define identity;
- perception and external content are evidence/context until canonical owners accept them;
- paid/external/consequential actions remain permission bounded;
- optional services must fail by degrading capability rather than preventing Core startup.

## Surfaces and capabilities

MaryV2 currently includes:

- canonical remote Core plus explicit standalone development mode;
- Desktop, mobile/PWA, native iPhone and terminal clients;
- Groq/Gemini/OpenRouter/Ollama routing plus explicit expert/provider paths;
- Ollama and llama.cpp local inference support;
- durable memory, relationship continuity, developed-self state and authored character evidence;
- voice/STT/TTS primitives, realtime interruption and sentence-level streaming primitives;
- avatar/VRM presentation, performer/stream contracts and browser/perception primitives;
- bounded distributed capability nodes and MCP integrations;
- experiential continuity, resumable workflow checkpoints, action verification and recovery;
- 13.8 relational presence: relationship mode, shared activities, proposal-only proactive presence, derived social graph and relationship-aware delivery.

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

Capability nodes are enrolled/run separately and remain replaceable resources.

## Product principle

The normal product should feel like Mary, not a backend dashboard. Ordinary screens emphasize conversation, presence, shared activity and useful context; provider/node/tool detail belongs in diagnostics. Desktop, native iPhone and PWA share one semantic/visual language while adapting layout to each device.

Historical package/install notes under `docs/history/` are provenance only and do not override current code, tests, `MARY_ROOT.md`, or active architecture documentation.
