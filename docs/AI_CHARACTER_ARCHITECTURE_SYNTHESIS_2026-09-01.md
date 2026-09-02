# MaryV2 AI Character Architecture Synthesis — 2026-09-01

## Purpose

This pass treats the public AI-character ecosystem as shared R&D material.  Mary is **not** being replaced by AIRI, Neuro, ProjectBEA, Lumi/Nox, Open-LLM-VTuber, Warashi, Riko, YuriOS, Chasm, or any other project.  The rule is: extract a useful mechanism, map it to Mary's existing canonical owner, preserve provenance/safety boundaries, integrate it vertically, then keep it only if it improves Mary.

Mary remains one canonical Core.  LLMs, LoRAs, nodes, avatars, stream clients, game bridges, and 3D stages are replaceable capabilities around that Core.

## Presence-first priority

1. Character / social presence
2. Realtime conversation and turn-taking
3. Behavior: notice / react / wait / initiate / ignore
4. Performance: voice / face / gaze / body
5. Perception and live-scene grounding
6. Learning, retrieval, model and LoRA evaluation
7. Embodiment: stream, game, VR/world, actor
8. Projects, tools, GUI and ecosystem surfaces in support of the above

## Reference-project synthesis

### Neuro-sama / official Neuro SDK

Public evidence is the game integration SDK, not Neuro's private cognitive implementation.  The useful public mechanism is **dynamic action availability**: a game exposes only actions that are valid now, with structured argument schemas; action selection and low-level execution remain distinct.

Mary integration:
- `mary.distributed.action_windows.ActionWindowRegistry`
- valid-current action windows with revision checks
- disposable actions disappear atomically before a selection can be repeated
- selection does not execute or bypass Mary's existing capability authorization
- current action windows enter bounded workspace context so cognition can reason over them

### ProjectBEA

Useful mechanism: one perception bus, deterministic direct-address handling, ambient salience, and **REACT / NOTE / DROP**.  NOTE becomes bounded peripheral awareness rather than an immediate LLM turn.  Cross-stage awareness can surface one-line "elsewhere, just now" context without merging places or minds.

Mary integration:
- existing `AttentionBus` upgraded; no second attention owner
- direct creator/addressed input deterministically reacts
- ambient input can react, become a peripheral note, or drop
- peripheral notes can be consumed once by the next relevant turn
- cross-surface stage notes feed workspace context
- private notes are forbidden from flowing into public/performance surfaces
- attention decisions are observable without storing raw private content

### Lumi / Nox

Useful mechanisms: speaker scheduling, one-voice-at-a-time arbitration, lightweight fast-brain decisions, cross-speaker stage awareness, bounded repeat-viewer familiarity, and high-level game planning separated from low-level pathfinding.

Mary integration:
- existing SpeechOutputArbiter remains the speech-floor owner
- Fast Brain remains an optional bounded classifier/ranker and never canonical cognition
- `AudienceRoster` adds session familiarity without becoming relationship truth
- cross-surface stage awareness is bounded and privacy-scoped
- action windows represent high-level available actions while game/world engines keep low-level movement

### AIRI

Useful mechanisms: typed plugin contracts, control-plane/data-plane separation, node capability discovery, IO tracing, VRM/Live2D stages, and proposed semantic motion retrieval/state-machine work.

Mary integration:
- existing control-plane / realtime-data-plane split remains canonical
- node capabilities stay truthful and typed
- behavior trace now covers attention, Fast Brain, speech arbitration, cross-surface awareness, and action windows
- `MotionLibrary` maps Mary's existing PerformancePacket semantics into presentation-only motion intentions
- motion binaries stay external/local; catalog metadata can later point at VRMA/FBX/BVH/Mixamo/custom clips

### Open-LLM-VTuber / Warashi

Useful mechanisms: interchangeable ASR/TTS/LLM backends, proactive speech, interruption/barge-in, visual perception, avatar expressions, long-term recall, current-world topics, quiet/sleep behavior.

Mary integration:
- preserve provider abstraction rather than adopting a monolith
- World Pulse remains expiring context, not identity/memory
- RealtimeInteraction + SpeechArbiter keep barge-in/floor ownership
- presence initiative remains bounded and silence is valid
- perception remains evidence/context, not authority

### Riko

The public repository demonstrates a comparatively small dialogue + TTS + STT + character configuration stack.  Any richer private implementation should be treated as unknown unless public evidence exists.  The lesson is that perceived character quality can come disproportionately from voice, timing, direction, and character consistency rather than subsystem count.

Mary integration:
- keep measuring experiential Mary-fit rather than rewarding architecture complexity
- Adapter Lab compares engines/LoRAs under the same Mary sourcebook grounding

### YuriOS

Useful mechanisms: always-on state ladder, auditable inner-life/journal, provenance-aware goals, reach-out gates, strong tool budgets, and the principle that a promise or background action should be inspectable rather than implied.

Mary comparison:
- Mary already has lifecycle/sleep, autonomy proposal safeguards, resource governance, experience journal, initiative gates, tool audit paths, and task workspaces
- do not create a duplicate mind loop or journal
- future improvement: explicit commitment/provenance view should reuse task/relationship/agency owners instead of accepting unsupported LLM promises

### Chasm / LLM NPC projects

Useful mechanism: characters know only what they personally witnessed, game bridges remain thin, and high-level character decisions are separated from game-engine execution.  Multi-NPC systems use a world/game-manager context rather than giving every character omniscience.

Mary integration direction:
- LiveScene/environment observations must retain source/provenance
- a future Mary World/Game bridge should expose semantic objects/actions and let engine navigation/IK execute low-level movement
- world observations never become creator truth simply because the game or VLM emitted them

### MotionMind and related motion systems

Useful mechanisms: video -> pose -> retarget -> motion cache, semantic indexing/retrieval, and physics/joint-safety validation before animation is used.

Mary integration:
- current semantic MotionLibrary is presentation-only
- future motion import should use a validator before a clip becomes eligible
- semantic metadata should be reusable across realtime avatar, scene performer, and virtual-world body

### Pipecat/TalkingHead-style companion pipelines

Useful mechanism: stream sentence chunks and synchronize avatar motion/lip sync to actual speech timing rather than using amplitude alone.

Mary integration:
- ElevenLabs provider now has an opt-in timestamp path (`MARY_TTS_ALIGNMENT=true`)
- provider-neutral character/word alignment enters the existing SpeechAudio metadata
- desktop avatar uses alignment timing to choose vowel mouth shapes while retaining amplitude for mouth intensity
- alignment is presentation metadata only and cannot enter identity/memory/cognition


## 2026-09-01 synthesis implementation checkpoint

This second pass moved several borrowed patterns from comparison notes into Mary's existing owners rather than creating parallel systems.

### Social-floor scheduling

- `RealtimeInteractionCoordinator` owns one `SpeakerScheduler`.
- Streaming Presence receives the exact same scheduler object.
- Creator/human floor has deterministic precedence.
- Direct/high-value ambient events can WAIT instead of interrupting; low-value ambient events can DROP.
- `SpeechOutputArbiter` still owns actual audio queue/drop/interrupt behavior; the scheduler only decides whether Mary should take conversational floor.

This synthesizes Lumi/Nox-style speaker scheduling with Mary's existing realtime/streaming owners.

### Causal realtime observability

- `RealtimeDecisionTrace` records bounded labels for attention, floor, speech and action-window decisions.
- It stores no raw dialogue, prompts, audio/images, identity, memory, secrets, or beliefs.
- Desktop and mobile project the same safe `Why Mary Did That` trace.
- Action windows, attention, speech and speaker scheduling share the same trace object.

This adapts AIRI-style IO/behavior observability while preserving Mary's authority boundaries.

### Confirmed VAD before barge-in

- Raw voice-activity onset can warm the listening path without interrupting Mary.
- Only confirmed speech claims creator floor and can barge in.
- False starts are counted and dismissed.

This specifically addresses a class of false-interruption failures seen in practical AI-character voice projects without changing Mary's explicit listening API.

### Capability readiness

- Device capabilities now distinguish `ready`, `degraded`, `starting`, and `unavailable`.
- Node routing only considers routable readiness states and prefers ready over degraded.
- Availability still does not grant permission or authority.

This closes the older class of `advertised but not actually executable` node mismatch.

### Semantic motion is now consumed by the body

- `PerformancePacket.motion_cues` no longer stop at metadata.
- The desktop VRM stage consumes semantic cues such as `explain_small`, `shrug_dry`, `teasing_point`, `thinking_pause`, `listen_attentive`, and `laugh_small` and maps them to bounded humanoid pose changes.
- These IDs are intentionally stable semantic slots so future VRMA/FBX/BVH assets can replace the procedural placeholder pose without changing Mary's actor/performance semantics.

This is the bridge from `Mary decided how to perform` to `the avatar actually changes its body`.

### Reproducible model / LoRA evaluation

- Adapter Lab can run local llama.cpp model/LoRA matrices with exact base-pair validation.
- Held-out creator-authored sourcebook grounding is used consistently across configurations.
- Blind review hides configuration identity.
- Human Mary-fit rubrics are explicitly separated from literal machine regression assertions; semantic phrases such as `natural direct response` are not incorrectly treated as required output strings.
- Experiment output cannot self-promote into canon, memory, relationship, developed self, or weights.

### Additional projects mined in the second sweep

- **Project Gabriel**: useful as a future VRChat embodiment reference — realtime native-audio model, CV/perception, OSC avatar control, memory, and surface independence.
- **Neocortex Unity SDK**: useful for future Mary World — tagged semantic scene objects, ordered per-line emotion/action delivery, group-scene roster, and a director deciding who speaks.
- **Emora**: independently validates a separate companion/performance brain that drives voice style, VRM expression, gaze and gestures instead of making the renderer infer acting from raw text. Mary's existing PerformancePacket/Performance Compiler remains the canonical owner.
- **Rexclaw**: useful continuity reference for one conversation that can move between voice and text while retaining history/tools/memory. Mary already follows this one-Core/many-surfaces principle.
- **Meuxe**: parallel per-segment TTS is a promising future latency optimization, but is deferred until live Mac timing data exists so cost/provider behavior is not changed blindly.
- **Chati**: true in-flight LLM/TTS cancellation during barge-in is a valuable future live-audio benchmark. Mary currently cancels presentation/speech state cleanly; provider-level generation cancellation should be added only through a provider-neutral cancellation contract rather than provider-specific hacks.
- **AITuber OnAir**: useful modular TypeScript AI-VTuber toolkit reference; mine component boundaries and stream/avatar ergonomics, not its application shell.

## Model / LoRA experimentation

Mary's Adapter Lab is intentionally an **experiment system**, not a model marketplace and not an identity owner.

Rules:
- weights live outside Git and canonical state
- candidates record source, license, base-model compatibility and hashes when available
- same held-out Mary prompts are run across model/adapter configurations
- each case is grounded with relevant creator-authored CharacterSourcebook records
- outputs are shuffled into a blind review set
- Melvin's blind scores are imported only into the Adapter Lab leaderboard
- no experiment output automatically changes Mary, memory, developed self, relationship, or training weights

Current useful comparison candidates include Qwen3 small/4B paths and Apache-2.0 SmolLM3 base/NPC-roleplay variants.  Candidate status means "worth testing," not "approved Mary model."

## Canonical-owner rule

When an external project has a feature Mary lacks, first ask whether Mary already has the correct owner:

- attention -> `AttentionBus`
- live environment -> `LiveScene`
- speaking floor -> `RealtimeInteraction` + `SpeechOutputArbiter`
- memory -> existing memory/reservoir/vector layers
- character -> Character Sourcebook / represented character systems
- relationship -> existing relationship system
- autonomy -> existing agency/autonomy governance
- tools -> existing capability/task/tool authorization
- performance -> existing PerformancePacket / expression layer
- devices -> existing NodeRegistry/capability contracts

Improve the owner.  Do not create `*_v2`, a parallel chatbot, or an external project's hidden authority.

## What remains genuinely live-test dependent

The deterministic architecture can be verified offline, but the following cannot be called proven until run on the actual Mac/Windows/stream/world hosts:

- comparative model/LoRA Mary-fit
- llama.cpp real latency on M1
- timestamped ElevenLabs lip-sync quality with Mary's actual voice
- natural barge-in and multi-speaker floor behavior under real audio
- Twitch/OBS live reconnect behavior
- future Unity/VRChat/world action bridges
- semantic motion quality after real animation assets are imported

Passing the release gate means the architecture is coherent and regression-safe.  It does not substitute for those experiential tests.
