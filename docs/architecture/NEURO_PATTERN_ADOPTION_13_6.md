# MaryV2 13.6 — AI-VTuber / Neuro-pattern adoption

This package converges the public AI-VTuber/companion patterns researched during the 13.1–13.5 work without turning Mary into a clone of another character or creating a second identity/runtime authority.

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

## Still deferred intentionally

- provider-specific token-stream adapters are opt-in work per provider; normal completion remains the fallback
- live Twitch OAuth/EventSub and OBS WebSocket sessions require creator credentials and host-side testing
- avatar/Unity/VRM motor adapters remain presentation capabilities, not identity authority
- LoRA/fine-tuning remains an explicit offline training workflow; Mary does not automatically train on conversation or feedback
- autonomous posting, moderation, purchases, shell execution and generic computer control are not granted by this package

## Architectural rule

The useful lesson from Neuro-like systems is not “copy the character.” It is to reduce latency, keep listening/speaking interruptible, isolate perception/action channels, make performer integrations replaceable, and preserve a durable character layer above whichever model is generating the current tokens.
