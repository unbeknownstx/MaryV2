# MaryV2 13.6 — AI-VTuber / Neuro-pattern adoption

This package converges the public AI-VTuber/companion patterns and separate performance/latency plans researched during the 13.1–13.5 work without turning Mary into a clone of another character or creating a second identity/runtime authority.

## Already adopted before 13.6

- one long-lived canonical Mary Core with replaceable surfaces/nodes
- secure enrolled capability nodes and device-local Ollama/llama.cpp execution
- attention arbitration and realtime interaction phases
- VAD candidate vs confirmed-speech handling, anti-echo and barge-in foundations
- persistent relationship/memory/personality/standing-affect continuity
- bounded perception with observation distinct from interpretation/memory truth
- hybrid lexical/vector retrieval plus contextual reranking
- explicit response feedback capture and evaluation/training evidence separation
- performance/presentation session primitives and stream-context trust boundaries

## Connected in 13.6

### Incremental generation → sentence speech

`mary.realtime.streaming` adds provider-neutral deltas, lossless sentence assembly and cooperative per-turn cancellation. It works with a one-shot provider as a one-delta fallback, so providers can adopt real token streaming incrementally without breaking Mary Core.

`mary.voice.streaming_tts` adds bounded synthesis-ahead with ordered playback. It depends on injected synth/play functions rather than a specific TTS service. Confirmed barge-in can cancel future queued speech through the same per-turn cancellation token; no process/thread kill or arbitrary execution is introduced.

### Retrieval quality evaluation

`mary.mind.retrieval_evaluation` measures hit-rate, precision/recall, reciprocal rank and nDCG, and can compare base vs contextual-reranked results. This evaluates derived retrieval quality only; it cannot promote a retrieved item into canonical memory truth.

### Performer / stream contracts

`mary.streaming` turns the previously documented Twitch/OBS environment settings into bounded contracts. Twitch audience text is explicitly `untrusted_audience` context. Outbound chat requires interactive mode plus `twitch.send_chat`. OBS accepts a finite set of read operations and two explicit write operations, with per-action permission requirements. There is no arbitrary OBS request passthrough.

Live Twitch EventSub/chat and OBS WebSocket transports remain node/surface adapters. They may reconnect or disappear without affecting Mary Core startup or identity/state authority.

### Turn latency evidence

`mary.runtime.turn_timing` implements the older latency-profiling plan as a secret-free deterministic primitive. It separates context/cognition/provider/reflection/retrieval/TTS/playback startup/tool timing instead of relying on a single end-to-end number. Surfaces can expose the breakdown locally without making an LLM call or storing prompt/memory content.

### Reclaimed 13.3.1 package components

A Library/repository reconciliation recovered useful code from the September 5 realtime/performance overlay that had never landed on GitHub. The surviving pieces are now connected to current 13.6 owners rather than copied wholesale:

- `mary.perception.browser` → existing `PerceptionDirector`, with URL/secret metadata sanitization
- `mary.game_control` → existing `NodeRegistry`, semantic intent only and never raw key/mouse control
- `mary.runtime.performance_profiles` → Core-owned resource policy, explicitly not identity/personality switching
- `mary.distributed.invocations` → process-local idempotency/retry coordination without execution authorization
- `mary.distributed.simulator` → deterministic development/test fake only
- `mary.realtime.brain_activity` → read-only causal/UI projection over the current realtime owner
- authenticated creator turns may wake an already-known sleeping surface, while explicit OFFLINE remains a hard gate

The old overlay's `SpeechSessionGuard` and `RealtimeSurfaceGate` were intentionally **not** restored. Current `PresentationSessionManager`, Mary Protocol replay/session isolation, durable node enrollment, and the existing realtime coordinator supersede them; restoring parallel guards would create duplicate lifecycle/transport authority.

## Still deferred intentionally

- provider-specific token-stream adapters are opt-in work per provider; normal completion remains the fallback
- live Twitch OAuth/EventSub and OBS WebSocket sessions require creator credentials and host-side testing
- exact runtime call sites will adopt `TurnLatencyProfiler` incrementally so timing does not destabilize the canonical turn path
- avatar/Unity/VRM motor adapters remain presentation capabilities, not identity authority
- LoRA/fine-tuning remains an explicit offline training workflow; Mary does not automatically train on conversation or feedback
- autonomous posting, moderation, purchases, shell execution and generic computer control are not granted by this package

## Architectural rule

The useful lesson from Neuro-like systems is not “copy the character.” It is to reduce latency, keep listening/speaking interruptible, isolate perception/action channels, make performer integrations replaceable, measure the real bottlenecks, and preserve a durable character layer above whichever model is generating the current tokens.
