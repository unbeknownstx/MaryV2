# MaryV2 System Registry

This registry is the current architectural index for MaryV2. Historical stage/release documents live under `docs/history/` and do not override this map.

Companion architecture maps: [data and authority flows](data_flow.md),
[13.2 reconciliation inventory](RECONCILIATION_13_2.md),
[13.4 MCP capability fabric](MCP_CAPABILITY_FABRIC_13_4.md),
[13.5 platform readiness](../operations/PLATFORM_READINESS_13_5.md),
[13.6 AI-VTuber / Neuro-pattern adoption](NEURO_PATTERN_ADOPTION_13_6.md),
[13.7 product experience convergence](PRODUCT_EXPERIENCE_13_7.md),
[13.8 relational presence/shared life](RELATIONAL_PRESENCE_13_8.md),
[13.9 native iPhone product](../design/NATIVE_IPHONE_PRODUCT_13_9.md),
[13.10 live stream cohost](STREAM_COHOST_13_10.md),
[13.11 home compute fabric](HOME_COMPUTE_FABRIC_13_11.md),
[13.12 bounded home sensor workers](HOME_SENSOR_WORKERS_13_12.md),
[13.13 public creator voice stream bridge](STREAM_SENSES_13_13.md), and
[13.14 character intelligence / learning interop](CHARACTER_INTELLIGENCE_LEARNING_13_14.md).

| Domain | Canonical implementation | Status | Authority / notes |
|---|---|---|---|
| Composition root | `mary.runtime.application.MaryApplication` | CANONICAL | One in-process Mary composition. |
| Remote authority | `mary.core.service.MaryCoreService` | CANONICAL | Owns one long-lived `MaryApplication` for remote clients. |
| Surface authority resolution | `mary.runtime.terminal`, `mary.desktop.authority`, mobile remote runtime | ACTIVE | `MARY_CORE_URL` means remote Core; no duplicate Mary. |
| Root invariants | `mary.runtime.root_authority` | CANONICAL | Executable one-Mary/context/capability rules. |
| Character bootstrap | `mary.character` / Character Core | CANONICAL | Compact fallback when no external authored source is active. |
| Authored character sources | `mary.character.sourcebook`, canonical `mary.character.CharacterSourcebook` | ACTIVE ENRICHED 13.14 | Loads approved sources from `character_sources/active/` or explicit env paths; canonical import adds typed provenance/authority projection without changing the authored source owner. |
| Character intelligence projection | `mary.character.intelligence` | ACTIVE READ-ONLY 13.14 | Typed claims, authority tiers, provenance edges and bounded evidence-collision diagnostics over already-selected sourcebook records. Projection only; no graph database, model output or external framework owns Mary. |
| Character evaluation | `mary.character.evaluation` | ACTIVE | Evaluation/training evidence only; not lived memory. |
| MaryBench / optimization interop | `mary.learning.interop`, `scripts.export_marybench` | ACTIVE LAB 13.14 | Exports existing evaluation cases as generic/DSPy/Promptfoo/Phoenix-compatible experiment records. Optimizer output is proposal-only and cannot mutate prompts, identity, memory or relationship automatically. |
| Relationship | `mary.relationship` | CANONICAL OWNER | Shared-history/creator relationship state. 13.8 relationship mode is represented through this same owner/history, not a second companion database. |
| Relational presence | `mary.relationship.relational_presence` | ACTIVE COMPOSITION 13.8 | `friend/close/romantic/partner`, bounded active shared activity, proposal-only presence impulses; durable changes delegate to canonical `RelationshipManager`. |
| Derived social graph | `RelationalPresenceRuntime.social_graph` | ACTIVE READ-ONLY 13.8 | Projection over canonical creator profile/history/shared experiences; no graph database or truth authority. |
| Social delivery projection | `mary.expression.social_delivery` | ACTIVE PRESENTATION 13.8 | Relationship/emotion-aware warmth/playfulness/intimacy/pace/energy hints; public scope suppresses private intimacy; providers cannot define relationship truth. |
| Memory | `mary.memory` | CANONICAL OWNER | Episodic/semantic/working memory. |
| Developed self / personality | `mary.personality`, growth paths | CANONICAL OWNER | Grounded development, not raw provider output. |
| Agency | `mary.agency` | CANONICAL OWNER | Goals, intentions, curiosities, priorities, decisions. |
| Autonomy | `mary.autonomy` | ACTIVE | Bounded execution/initiative; capability != permission. |
| Emotion/expression | `mary.expression` | ACTIVE | Baseline + state + momentum/decay; does not own personality. |
| Turn context | `mary.cognition.mind_state`, continuity/context modules | CANONICAL TURN LAYER | Bounded current/recent/retrieved/authored context; canonical relationship-history summary includes explicit 13.8 relationship mode. 13.14 structured sourcebook evidence enters through the same existing authored-character context field. |
| Reasoning/cognition | `mary.cognition` | ACTIVE | Provider-independent Mary reasoning orchestration. |
| Provider routing | `mary.llm.router` | ACTIVE | Free/cheap/private/expert routes; models never own identity. |
| OpenAI expert | `mary.llm.providers.openai`, orchestration consultation | ACTIVE, EXPLICIT | Paid specialist route only with authorization. |
| Ollama local/private | Ollama provider + device-node executor | ACTIVE | Optional local capability; headless Windows node supported. |
| Research/evidence | `mary.learning`, `mary.tools.web` | ACTIVE | External evidence remains provenance-bearing and temporary until accepted. |
| Retrieval/reservoir | `mary.mind` | ACTIVE SUPPORT | FTS/vector/cache layers are derived, not truth authority. |
| Tool permissions | `mary.tools`, `mary.distributed.permissions` | CANONICAL BOUNDARY | Consequential actions remain gated; MCP requires capability + exact tool allowlists. Sensor capabilities are default-deny local permissions. |
| Compute nodes | `mary.distributed`, `mary.desktop.device_node` | ACTIVE | Nodes advertise/execute capabilities; never own Mary. |
| Home compute fabric | `mary.distributed.compute_fabric`, `mary.distributed.benchmarking`, `scripts.run_home_node` | ACTIVE OPTIONAL 13.11 | Benchmark-aware Mac/Windows/Linux worker selection and cross-platform node hosting; benchmark/resource data is disposable operational evidence only and never grants execution authority. |
| Runtime resource profiling | `mary.distributed.resource_profile` | ACTIVE HINT 13.11 | CPU/memory/Metal/Vulkan/local-runtime visibility and optional GPU labels/VRAM hints guide empirical testing only; hardware presence is not permission or proof of useful acceleration. |
| Home sensor workers | `mary.distributed.sensors`, `mary.distributed.sensor_node` | ACTIVE OPTIONAL 13.12/13.14 | Default-deny typed `sensor.audio_transcribe`, `sensor.screen_capture`, and 13.14 `sensor.screen_describe`. Audio/screens/visual descriptions are ephemeral evidence, never memory truth or action authority. |
| Specialist STT bridge | `mary.desktop.stt` | ACTIVE OPTIONAL 13.14 | Existing Groq/faster-whisper/whisper.cpp plus device-configured Qwen3-ASR/FluidAudio/specialist HTTP. Only loopback HTTP or HTTPS; task payloads cannot choose provider URL/model path/executable. |
| Semantic screen perception | `sensor.screen_describe` in `mary.distributed.sensors` | ACTIVE OPTIONAL 13.14 | Bounded local screenshot -> preconfigured llama.cpp-mtmd or OmniParser semantic description. No mouse/keyboard/click/action authority and no automatic memory write. |
| Specialist backend catalog | `mary.distributed.specialist_catalog`, `scripts.check_specialist_backends`, platform readiness | ACTIVE DISCOVERY 13.14 | Read-only readiness vocabulary for FluidAudio, Qwen3-ASR, TEN VAD, Chatterbox, llama.cpp mtmd, OmniParser, Graphiti, DSPy/GEPA, Phoenix, Promptfoo, Unsloth and Axolotl. External specialists never become Core startup or identity/memory authority. |
| MCP capability fabric | `mary.distributed.mcp_fabric`, `mary.desktop.device_node` | ACTIVE OPTIONAL 13.4 | OpenDesign/Scrapling/Langflow over preconfigured Streamable HTTP(S); node-local credentials, lazy discovery, exact tool allowlists, sanitized results; no shell/stdio launcher. |
| Incremental response / sentence TTS | `mary.realtime.streaming`, `mary.voice.streaming_tts` | ACTIVE PRIMITIVES 13.6 | Provider-neutral deltas, sentence assembly, cooperative cancellation, bounded ordered synthesis-ahead; one-shot providers remain valid. |
| Performer integrations | `mary.streaming.bridge`, `mary.streaming.config` | ACTIVE CONTRACT 13.6 | Twitch input is untrusted audience context; outbound chat/OBS writes require explicit bounded permissions. |
| Stream chat coordination | `mary.streaming.presence`, `mary.streaming.chat`, `mary.streaming.input_governor`, `mary.streaming.output` | ACTIVE 13.6/13.10 | Core-owned dedupe, hostile/injection filtering, audience scoring, creator-floor arbitration and drop/react/wait/chat/speak/both planning. Chat never gains creator/tool authority. |
| Live stream cohost | `mary.streaming.cohost`, `scripts.run_stream_cohost` | ACTIVE OPTIONAL 13.10 | Selected Twitch messages become bounded public-safe canonical Core turns; runner registers one creator surface and scopes only that device to `stream` performance context. No second Mary/chatbot loop. |
| Public creator stream voice | `mary.streaming.creator_audio`, `scripts.run_stream_creator_voice` | ACTIVE OPTIONAL 13.13 | Explicitly armed VAD microphone -> bounded `sensor.audio_transcribe` -> same canonical `stream-public` conversation -> Core TTS / loopback OBS relay. Private Desktop conversation is never mirrored into public stream context. |
| OBS audio/caption relay | `mary.streaming.relay` | ACTIVE PRESENTATION 13.10 | Loopback-only Browser Source transport for latest bounded Core TTS audio + caption; contains no Core/Twitch credentials or canonical state. |
| Twitch EventSub transport | `mary.integrations.twitch_eventsub`, `mary.integrations.twitch_runtime` | ACTIVE OPTIONAL | Current chat EventSub normalization/session continuity, self-echo and outbound rate/dedupe contracts; transport-only. |
| Twitch typed chat send | `mary.integrations.twitch_chat`, `TwitchChatOutbox` | ACTIVE OPTIONAL 13.10 | Current bounded Send Chat Message request shape + existing rate/dedupe planner; write path requires explicit configuration/token scope and never authorizes tools. |
| Capability invocation coordination | `mary.distributed.invocations` | ACTIVE SUPPORT 13.6 | Process-local idempotency/retry primitive only; no authorization and no canonical-result authority. |
| Capability simulator | `mary.distributed.simulator` | TEST/DEVELOPMENT 13.6 | Deterministic fake adapter only; never registers as Mary. |
| Semantic game control | `mary.game_control` | ACTIVE ROUTING CONTRACT 13.6 | High-level intent routes through NodeRegistry; raw key/mouse execution excluded and device permission still required. |
| OpenHands engineering worker | `docs/architecture/OPENHANDS_WORKER_BOUNDARY_13_4.md` | DESIGNED SEPARATE | Sandboxed software-engineering worker boundary; proposal/patch output only, no Mary identity/Core authority, no automatic merge. |
| Platform readiness | `scripts.platform_readiness`, `requirements-host-extras.txt` | ACTIVE OPTIONAL 13.5/13.14 | Read-only Mac/Windows/Linux capability/config presence plus specialist readiness; optional packages/services never gate Core startup; no shell execution. |
| Experience quality telemetry | `mary.runtime.experience_quality`, `mary.runtime.performance_hardening` | ACTIVE READ-ONLY 13.7 | Content-free rolling latency/outcome classification; explicitly no identity, memory, routing, lifecycle or permission authority. |
| Experience projector | `mary.experience.projector` | ACTIVE PRESENTATION 13.8 | Whitelisted `/api/experience` projection surfaces explicit close/romantic/partner mode from Core while keeping provider/secrets/non-authoritative fields out. |
| Visual/product design contract | `docs/design/MARY_VISUAL_SYSTEM.md` | ACTIVE CONTRACT 13.7 | Shared semantic color/motion/degraded-state language for surfaces; presentation only. |
| Relational UI contract | `docs/architecture/RELATIONAL_PRESENCE_UI_13_8.md`, `desktop/public/relational-13-8.css` | ACTIVE CONTRACT 13.8 | Shared-life cards/actions, privacy projection and anti-attention-trap styling; normal product surfaces remain creator-facing rather than backend dashboards. |
| Native iPhone product contract | `docs/design/NATIVE_IPHONE_PRODUCT_13_9.md` | ACTIVE CONTRACT 13.9 | Home/Talk/Together/Work/More prioritize companion presence and shared context; approved bundled Mary art + SF Symbols; no copied competitor assets or mobile-owned relationship authority. |
| Windows headless node | `scripts.run_windows_node` | ACTIVE | Can expose Ollama without Desktop UI. |
| Cross-platform home node | `scripts.run_home_node` | ACTIVE 13.11/13.12 | Preferred headless Mac/Windows/Linux worker host; reuses durable enrollment, local device permissions, bounded task executors, optional sensor workers and benchmark metadata. |
| Desktop | `mary.desktop`, `desktop/` | ACTIVE POLISHED 13.8 | Presentation/capability surface; 13.7 responsive/portrait-safe base plus 13.8 relational visual layer. |
| Mobile/PWA | `mary.mobile`, `mobile_web/` | ACTIVE POLISHED 13.8 | Remote Core surface; existing presence rail receives relationship mode through the shared experience projector without owning state. |
| Native iPhone | `ios/MaryV2iOS/` | ACTIVE PRODUCT 13.9 | SwiftUI surface over canonical Core with Keychain auth, local push-to-talk transcription, Core voice playback, relational projection, conversation-first Talk, Together shared-life UX, native haptics/accessibility and preserved Work/Focus. |
| Legacy native mobile | `mobile_native/` | PARTIAL / COMPATIBILITY | Retained wrapper kept byte-aligned with the compatibility PWA where tests require it; does not override SwiftUI or Core authority. |
| Voice/STT/TTS | `mary.voice`, `mary.desktop.voice`, audio modules | ACTIVE | Provider/local voice capability + performance direction. Stream cohost reuses authenticated Core voice synthesis rather than owning a TTS provider. 13.14 catalogs Chatterbox but does not promote it ahead of existing ElevenLabs/Piper/SAPI without local benchmark evidence. |
| Avatar/embodiment | `mary.avatar`, desktop presentation | ACTIVE BASELINE | Current VRM/stage is baseline, not final expressive ceiling; stream cohost is renderer-neutral so future Live2D/2.5D/3D bodies can consume the same speech/attention/performance state. |
| Perception | `mary.perception` | ACTIVE BOUNDED | Describe observation before Mary interprets; no automatic memory truth. Stream responses may read a small secret-filtered current summary. 13.14 semantic screen evidence should publish through this same perception boundary when used by a surface. |
| Browser context sensor | `mary.perception.browser` | ACTIVE BOUNDED 13.6 | Page/media summaries enter PerceptionDirector after URL/metadata sanitization; no browser-owned memory/personality. |
| Runtime performance profiles | `mary.runtime.performance_profiles` | ACTIVE POLICY 13.6 | Light/balanced/performance resource targets only; explicitly cannot switch identity. |
| Realtime activity projection | `mary.realtime.brain_activity` | ACTIVE READ-ONLY 13.6 | Bounded floor/attention/decision labels for UI/debugging; no chain-of-thought or write authority. |
| Turn latency evidence | `mary.runtime.turn_timing` | ACTIVE DIAGNOSTIC 13.6 | Secret-free named stage timings; diagnostic only. |
| Retrieval evaluation | `mary.mind.retrieval_evaluation` | ACTIVE EVALUATION 13.6 | Ranking quality metrics over derived retrieval; cannot promote memory truth. |
| Creative Studio | `mary.creative`, `mary.desktop.projects` | ACTIVE BASELINE | Cross-media planning/workspace with creator provenance and approvals. |
| Creative services | `mary.creative.services` | ACTIVE CONTRACT | Capability/cost discovery; real vendor execution adapters remain service-specific. |
| Unbeknownst workspace | `projects/unbeknownst/` | CANONICAL PROJECT HOME | Book/manga/animation/audio/assets/production organization. |
| Recovery | `mary.runtime.recovery`, recovery scripts | ACTIVE BASELINE | Secret-free manifests/snapshots; derived state rebuildable. |
| State reconciliation | `mary.runtime.state_reconciliation` | ACTIVE READ-ONLY | Single root = inventory only; two+ roots required for comparison. |
| Repository structure | `scripts.verify_repository_structure` | CANONICAL HYGIENE GATE | Prevents payload/data/node_modules/history drift into active root. |
| Historical development | `docs/history/` + Git history | ARCHIVE | Provenance only; never current runtime authority. |

## Release blockers still intentionally open

- Continue approving/expanding the Character Bible/corpus and move approved material into `character_sources/active/`; 13.14 now projects richer typed provenance from whatever source material is approved.
- Expand Mary-specific character evaluation substantially from authored examples; `scripts.export_marybench` now makes those cases portable to external experiment/optimizer tooling without granting it write authority.
- Add real authorized adapters for selected image/video/audio generation services.
- Mature avatar/3D expression beyond the current baseline model; Live2D/2.5D/3D stream bodies should attach to the existing cohost/voice/performance state rather than creating another runtime.
- Benchmark FluidAudio/Qwen3-ASR/Whisper variants, llama.cpp-mtmd/OmniParser perception and Chatterbox versus existing routes on representative creator hardware. Presence in the 13.14 specialist catalog is not promotion.
- Add authenticated creator-facing mutation controls for relationship mode/shared activities through the existing bounded Core action path; do not bypass the single-writer Core for UI convenience.
- Feed the social-delivery envelope into the winning real TTS/avatar adapters only after provider-specific behavior is tested.
- Replace the bounded stream speech-duration estimate with explicit renderer/browser playback completion acknowledgement if stream-floor timing proves materially inaccurate in live testing.
- Continue live cross-device/Core/node/Twitch/OBS testing under real provider/network failures and collect operational latency/readiness evidence.
- Establish an intentional production continuity dataset after development/test state is discarded.
