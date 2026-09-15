# MaryV2

**Many surfaces. Many capability nodes. One persistent Mary.**

MaryV2 is a local-first, cloud-capable persistent character runtime. Mary is not a wrapper around one language model: identity, authored character evidence, relationship continuity, memory, developed self, agency, expression, permissions, realtime coordination, tools, and capability routing remain explicit systems around replaceable models and devices.

## Current architecture

MaryV2 through 13.64 keeps one canonical Mary Core while treating models, gateways, local engines and compute nodes as replaceable execution resources. The provider and model stack is now one cohesive pipeline rather than a sequence of independent extensions:

`GenerationRequest -> hard router eligibility -> ResourceGovernor operational evidence -> bounded provider execution -> normalized response`

The existing 13.15 provider catalog supplies creator/configuration-approved frontier/open-model metadata. The 13.35+ Model Execution Fabric classifies discovered, reachable, feasible, suitable and preferred compute by task. The 13.37–13.59 reliability/home-compute work adds qualified model identities, measured correctness/useful throughput, resource fit, live telemetry, load-aware routing, calibration provenance and explainable adaptive decisions. The 13.60–13.64 provider work adds health, quota, pressure, hysteresis, bounded failover, endpoint policy, catalog trust, provider-substitution detection, compatible embedding failover and transport capability checks. These are all operational evidence below Mary Core authority; none owns identity, memory, relationship, goals, permissions or developed self.

FreeLLMAPI-derived engineering is integrated as patterns inside Mary's provider/model fabric, not as a second brain or mandatory service. A FreeLLMAPI instance may be used as an optional OpenAI-compatible gateway just like another replaceable endpoint. Direct Groq/Gemini/OpenRouter/frontier routes, Ollama/llama.cpp, local capability nodes and optional gateways can coexist because Mary owns authorization and selection above them.

13.34 defines the **Computational State Fabric** for canonical/rebuildable/warm/ephemeral state. 13.35 defines the **Model Execution Fabric** for task-aware suitability. 13.36 adds the **MaryOS Linux substrate** without moving Core authority or introducing arbitrary shell/root execution. Later reliability and provider revisions extend those fabrics rather than creating new authority layers.

MaryV2 13.29–13.33 forms a bounded cognitive research/execution layer: adaptive deliberation budgets, pass/verify/branch execution, non-mutating memory-action selection, content-free trajectory telemetry, proposal-only experience-informed strategy selection and duplex-conversation policy. These systems do not expose private chain-of-thought or automatically self-modify production Mary.

The native iPhone companion, PWA/Desktop/terminal surfaces, Twitch/OBS cohost, bounded MCP integrations, home compute/sensor nodes and future MaryOS/creator surfaces all remain projections or capabilities of the same Core.

See:

- `MARY_ROOT.md` — canonical authority rules
- `docs/README.md` — documentation map
- `docs/architecture/SYSTEM_REGISTRY.md` — current system registry
- `docs/architecture/FREELLMAPI_INTEGRATION_13_64.md` — unified provider/model execution fabric and 13.60–13.64 boundary
- `docs/architecture/MODEL_EXECUTION_FABRIC_13_35.md` — task-aware model/node feasibility and promotion policy
- `docs/architecture/OPEN_MODEL_FABRIC_13_15.md` — frontier/open-model provider catalog and direct routes
- `docs/architecture/COMPUTATIONAL_STATE_FABRIC_13_34.md` — durability/cache/recovery architecture
- `docs/architecture/MARYOS_LINUX_SUBSTRATE_13_36.md` — Linux/systemd host substrate and future MaryOS boundary
- `docs/architecture/RESEARCH_CONVERGENCE_13_29_13_32.md` — cognitive research convergence and promotion boundary
- `docs/architecture/COGNITIVE_EXECUTION_13_33.md` — bounded pass/verify/branch execution and proposal-only strategy evidence
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
- provider catalogs describe routes; they do not authorize them;
- health, quota, latency, benchmarks and resource fit are operational evidence, not Mary state;
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
- benchmark-aware Mac/Windows/Linux home compute nodes with disposable operational profiles and cross-platform launch tooling;
- a MaryOS Linux substrate with read-only host discovery and an optional systemd user-service path;
- explicit opt-in home-node STT and bounded screen-capture workers for realtime/perception pipelines;
- Groq/Gemini/OpenRouter/Ollama routing plus explicit expert/provider paths;
- an opt-in frontier/open-model catalog for DeepSeek, Z.AI/GLM, Qwen, Kimi, MiniMax, Cerebras, Together, Fireworks and future compatible services;
- a unified provider operational layer for health, quota, pressure, hysteresis, bounded failover, readiness, endpoint policy and content-free analytics;
- qualified model/route identity, benchmark-before-promotion, task-lane suitability, resource-fit calibration and explainable adaptive routing;
- optional OpenAI-compatible gateways, including a separately operated FreeLLMAPI gateway, without making them Core dependencies;
- independent compatible-space embedding failover plus existing vector-index identity protections;
- Ollama, llama.cpp and compatible loopback local inference support;
- durable memory, relationship continuity, developed-self state and authored character evidence;
- voice/STT/TTS primitives, realtime interruption and sentence-level streaming primitives;
- avatar/VRM presentation, performer/stream contracts and browser/perception primitives;
- bounded distributed capability nodes and MCP integrations;
- experiential continuity, resumable workflow checkpoints, action verification and recovery;
- adaptive per-turn deliberation planning with bounded pass/branch/verifier budgets and no chain-of-thought persistence;
- bounded cognitive execution for single-pass, verify-once and branch/verify workflows;
- proposal-only strategy advice from structural outcome evidence rather than raw private reasoning;
- non-mutating memory-action policy plus temporal/provenance projections over canonical memory owners;
- content-free trajectory telemetry for future MaryBench/offline optimization, never automatic production training;
- optional research-runtime discovery for latent reasoning, vLLM/SGLang, mobile inference, distributed inference, realtime transports, A2A and offline RL;
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

MaryOS/Linux host readiness (read-only):

```bash
python -m scripts.maryos_status
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
