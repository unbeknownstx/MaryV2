# MaryV2 13.7 — Product Experience + Open-Source Research Convergence

## Goal

13.7 is a cohesion release, not another identity/core rewrite. Mary already has the difficult ownership boundaries: one canonical Core, persistent character/relationship/memory/developed-self owners, replaceable provider and node capabilities, bounded autonomy, realtime coordination and native/web/desktop surfaces.

The remaining product problem is that those systems must **feel like one responsive companion** instead of exposing their implementation history.

## Research patterns worth adopting

Current open-source local companion/VTuber systems repeatedly converge on the same engineering lessons:

1. **One stable realtime pipeline.** VAD/STT/LLM/TTS/avatar components should have explicit lifecycle/readiness/degraded states instead of each surface guessing whether a backend is usable.
2. **Measure perceived latency.** Track first useful feedback and end-to-end turn timing. Optimize pipeline placement, streaming/chunking and warmup before swapping entire architecture stacks.
3. **Stream sentences, not monolithic responses.** Incremental generation + sentence-oriented synthesis lowers first-audio latency while preserving ordered playback and cancellation.
4. **Barge-in is a first-class lifecycle event.** Confirmed human speech should cancel future Mary speech without killing processes or creating a second conversation owner.
5. **Schemas at capability boundaries.** Browser/avatar/game/tool adapters should exchange bounded semantic events/actions rather than arbitrary commands or duplicated application state.
6. **Local-first should degrade gracefully.** A missing GPU, renderer, TTS engine, MCP server or node should reduce a capability—not prevent Mary Core from existing.
7. **Keep the avatar/render loop separate from cognition.** High-rate viseme/gaze/motion updates belong in the presentation/data plane; identity and reasoning stay in canonical Core.

## Mary 13.7 implementation

### Experience quality telemetry

`mary.runtime.experience_quality.ExperienceQualityMonitor` introduces a content-free rolling operational vocabulary: `instant`, `responsive`, `delayed`, `degraded`. It retains latency/outcome labels only and has **no identity, memory, provider-routing, lifecycle or permission authority**.

It is attached through the existing `PerformanceHardeningBundle` so surfaces can progressively show meaningful experience health without creating another diagnostics owner.

### Visual system convergence

Desktop, SwiftUI and PWA use the same product principles:

- dark navy/black environmental base;
- Mary pink/magenta as character/relationship accent;
- violet for cognitive/continuity depth;
- cyan/blue for capability/live-system information;
- restrained glass/HUD surfaces;
- creator-generated Mary art as the canonical visual fallback language;
- animation used as state feedback rather than decoration;
- reduced-motion and renderer fallback as normal supported states.

See `docs/design/MARY_VISUAL_SYSTEM.md`.

### Version/source-of-truth cleanup

Public docs and live product labels must reflect the current architecture. Old `12.x`/`13.3` presentation labels are historical; they should not make a 13.7 source tree look like several products at once.

## Adopt later / benchmark first

These are promising but intentionally **not mandatory dependencies** in 13.7:

- Pipecat-style orchestration for experimental local voice pipelines;
- faster-whisper/whisper.cpp/Parakeet comparisons for local STT;
- Kokoro/Piper/other local TTS comparisons against Mary's actual voice requirements;
- WebRTC/Opus low-latency transport where browser/mobile network topology benefits;
- browser WebGPU inference as a capability-node/surface experiment;
- RVC/voice conversion only when latency, licensing and identity/voice provenance are acceptable;
- richer multi-speaker floor estimation and contextual prosody;
- local VLM perception after hardware supports it comfortably.

Mary should benchmark these behind existing provider/capability contracts rather than making a framework swap the architecture.

## Explicitly rejected patterns

- An LLM/model becoming Mary's identity owner.
- A UI, avatar or node persisting canonical relationship/memory state independently.
- Autonomous shell/computer control hidden inside a generic plugin.
- Untrusted stream/chat/browser text becoming memory truth by default.
- Mandatory cloud service dependencies at Core startup.
- Training automatically on conversation merely because feedback exists.
- Copying third-party character/UI art into Mary without clear licensing/provenance.

## Product acceptance direction

A polished Mary release should be evaluated as a lived product path:

1. Core starts with optional capabilities absent.
2. Desktop/iPhone/PWA connect to the same instance and show the same current Mary state.
3. Chat works before optional avatar/voice/node services finish warming.
4. Voice transitions cleanly through listening/transcribing/thinking/speaking and handles confirmed interruption.
5. Optional local nodes appear/disappear without identity discontinuity.
6. Public/performance mode cannot leak private creator context.
7. UI exposes useful status, not backend implementation noise.
8. Reduced-motion/portrait/degraded modes remain fully usable.
9. Repository docs explain this architecture without requiring historical patch archaeology.
