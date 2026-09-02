# Character-runtime research — 2026-09-01

This pass studied public/open projects to identify proven patterns worth adapting into MaryV2. It is architecture mining, not a fork/replacement strategy.

## ProjectBEA pattern

Useful idea: many perception sources feed one bounded attention layer, where events can be acted on, merely noted, or dropped. Mary’s existing `AttentionBus` plus Presence now gains a `LiveScene`, FastBrain reranking, and pending-thought continuity rather than starting another background chatbot loop.

Reference: https://github.com/emqnuele/projectBEA

## AIRI pattern

Useful idea: separate a control plane (lifecycle, capability/permission/control traffic) from a high-rate data plane (audio/vision/telemetry). Mary now has an explicit bounded `RealtimeDataPlane` beside existing typed Core actions/capability nodes.

References:
- https://github.com/moeru-ai/airi
- https://github.com/moeru-ai/airi/blob/main/packages/plugin-sdk/docs/design/architecture.md

## Live AI-character / VTuber patterns

Useful recurring ideas across public projects:
- a single speech/output arbiter rather than every TTS producer talking independently;
- cheap attention/ranking before expensive generation;
- barge-in and turn ownership;
- proactive behavior based on event significance instead of a timer alone;
- local/cloud components that can be swapped without changing character identity.

References:
- https://github.com/coco-research/open-llm-vtuber
- https://github.com/inni918/warashi

## llama.cpp

Useful today because it provides a local OpenAI-compatible server and supports GGUF models plus multiple loaded LoRA adapters. The server API supports per-request LoRA scaling, which fits Mary’s Adapter Lab: adapters are measurable generation influences rather than identity owners.

Reference: https://github.com/ggml-org/llama.cpp/tree/master/tools/server

## Reviewed model experiments

### Qwen3 1.7B Q4_K_M

- repo: `ggml-org/Qwen3-1.7B-GGUF`
- artifact: `Qwen3-1.7B-Q4_K_M.gguf`
- approx size: 1.28 GB
- SHA256: `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5`
- use: cheap Mac/local specialist or FastBrain experiment, not assumed primary Mary model

Source: https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/blob/main/Qwen3-1.7B-Q4_K_M.gguf

### Generic roleplay LoRA candidate

- repo: `rockerBOO/qwen3-4b-roleplay-lora-F16-GGUF`
- artifact: `qwen3-4b-roleplay-lora-f16.gguf`
- size: 11.8 MB
- SHA256: `d764e4f69052ba9f87cc75140ca13e3860eb30890b87c0b12aa17d419ed8bbf5`
- license: Apache-2.0
- exact upstream base: `p-e-w/Qwen3-4B-Instruct-2507-heretic`
- trained from ~7.69k roleplay conversations
- LoRA rank 8, alpha 16

Sources:
- https://huggingface.co/rockerBOO/qwen3-4b-roleplay-lora
- https://huggingface.co/rockerBOO/qwen3-4b-roleplay-lora-F16-GGUF

### Exact compatible Q4_K_M base candidate

- repo: `bartowski/p-e-w_Qwen3-4B-Instruct-2507-heretic-GGUF`
- artifact: `p-e-w_Qwen3-4B-Instruct-2507-heretic-Q4_K_M.gguf`
- approx size: 2.50 GB
- SHA256: `d4d7fcd11d36495fa340f91b514ae3a47f5da21cf27c158d620d736e3bb35a61`
- license: Apache-2.0

Source: https://huggingface.co/bartowski/p-e-w_Qwen3-4B-Instruct-2507-heretic-GGUF

## Local voice / Apple ecosystem

`sherpa-onnx` documents offline real-time speech recognition on iPhone/iPad, while Silero VAD is MIT-licensed and portable through ONNX Runtime. `whisper.cpp` supports Apple platform builds including Metal/CoreML-related paths. Mary therefore treats these as optional device-local capabilities rather than requiring a cloud-only speech stack.

References:
- https://github.com/k2-fsa/sherpa-onnx
- https://github.com/snakers4/silero-vad
- https://github.com/ggml-org/whisper.cpp

## Resulting MaryV2 architecture decisions

1. Keep one canonical Mary Core.
2. Make high-rate realtime input ephemeral and bounded.
3. Project all clients into one Core-owned Live Scene.
4. Keep creator conversational floor as a deterministic hard rule.
5. Let a FastBrain rank attention, never grant authority.
6. Use a speech arbiter for queue/drop/interrupt semantics.
7. Bring current-world context into cognition with TTL/source attribution.
8. Contextually rerank existing canonical-memory hits rather than replacing memory.
9. Make local models/LoRAs optional providers behind existing routing.
10. Evaluate premade and Mary-trained adapters against the same Mary-specific held-out suite.
## Second-sweep implementation references

### Project Gabriel Remastered

Useful pattern: a VRChat-oriented AI companion can still keep VRChat optional and expose the same character through other surfaces. Its public design combines realtime native audio, CV/perception and OSC avatar control. Mary should use this as a future embodiment bridge reference, not as an identity/runtime replacement.

Reference: https://github.com/HoppouAI/ProjectGabriel-Remastered

### Neocortex Unity SDK

Useful pattern: tagged objects provide semantic scene perception; responses can carry ordered line-level emotion/actions; multi-character scenes use a roster and an explicit speaking director. This strongly matches Mary's future `Mary World` direction and current shared `SpeakerScheduler`.

Reference: https://github.com/neocortex-link/neocortex-unity-sdk

### Emora / AI Companion

Useful pattern: a dedicated companion-behavior layer drives voice style, expression, gaze, gesture, listening/thinking states and VRM motion. Mary already has the correct owner in PerformancePacket/Performance Compiler; the lesson is to keep making that layer physically observable in the body rather than relying on text-tag inference in the renderer.

Reference: https://github.com/MaheshReddy-ML/AI-Companion

### Rexclaw

Useful pattern: voice and text are modes of one ongoing conversation rather than separate histories. Mary already targets this through canonical Core conversation state and cross-surface clients.

Reference: https://github.com/Codemarchant/rexclaw

### Meuxe

Useful pattern: parallel TTS synthesis of response segments can reduce perceived latency. This remains deferred until Mary has live Mac latency traces; it should reuse PerformancePacket segmentation and SpeechOutputArbiter rather than create another speech pipeline.

Reference: https://github.com/meet447/Meuxe

### Chati

Useful pattern: on barge-in, stop TTS, cancel the in-flight generation, and preserve enough interrupted context for the next turn. Mary now has confirmed-VAD gating and bounded interruption state; provider-neutral generation cancellation remains a future improvement because current providers do not expose one uniform cancellation contract.

Reference: https://github.com/ekontoTURBO/chati-project

### AITuber OnAir

Useful pattern: modular AI-VTuber packages for chat, voice, memory and VRM/Live2D rather than one inseparable application. Mary should continue mining package boundaries and stream UX while keeping Mary Core as the only canonical owner.

Reference: https://github.com/555rrw/aivuber-onair-pro

## Current synthesized mechanisms now implemented

- one shared social-floor `SpeakerScheduler` across realtime and Streaming Presence;
- REACT/NOTE/DROP attention with bounded peripheral awareness;
- bounded cross-surface `elsewhere, just now` notes;
- safe realtime causal decision trace;
- confirmed-VAD gate before interruption;
- node capability readiness-aware routing;
- dynamic action windows with revision/disposable-action semantics;
- session-only audience familiarity;
- semantic motion slots now consumed by the desktop VRM body;
- reproducible/blinded Adapter Lab scoring with human-rubric vs literal-regression separation.

These mechanisms all attach to existing Mary owners. None creates a second Mary, memory authority, relationship authority, cognition loop, or speech pipeline.
