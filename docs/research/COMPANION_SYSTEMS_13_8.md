# MaryV2 13.8 Companion / VTuber / Agent Research Notes

This document records implementation-relevant patterns from public companion, VTuber, memory, realtime-voice, agent and embodiment projects. It is intentionally architecture-focused rather than a feature-copy list.

## Strong patterns worth adopting

### AIRI-style event separation
- Keep cognition/control messages separate from high-rate render/audio/game data.
- Treat plugins and embodiments as capabilities, not identity owners.
- Prefer explicit transport contracts over surface-specific special cases.

### Open-LLM-VTuber interaction patterns
- Desktop-pet presentation can create strong ambient co-presence without changing Core authority.
- Voice interruption, self-echo resistance and touch/click reactions matter disproportionately to perceived aliveness.
- LLM, ASR, TTS and renderer adapters should remain replaceable.

### Pipecat realtime patterns
- Turn detection needs more than a silence timer.
- Barge-in should cancel generation/synthesis/playback coherently.
- Measure conversational timing stages rather than only total model latency.

### Letta / MemGPT memory separation
- Keep small high-value identity/context state distinct from large archival memory.
- Context packing should be selective and evidence-driven.

### Mem0 / GraphRAG relationship projections
- Entity/relationship structure can improve retrieval when used as a projection over canonical source data.
- A graph should not silently become truth authority or overwrite explicit creator facts.

### Local companion community patterns
- Hybrid local/cloud execution works best when each stage can degrade independently.
- Avatar presence, local STT/TTS and lightweight background state machines often add more product value than another giant agent loop.
- Reflection/diary passes are useful only when their outputs remain proposals until governed acceptance.

## Mary-specific synthesis

The differentiated MaryV2 architecture is:

1. Persistent character at the center.
2. Canonical relationship/memory/developed-self owners around that character.
3. Realtime cognition and perception as replaceable runtime capabilities.
4. Capability nodes and tools outside the identity boundary.
5. Multiple embodiments and surfaces as projections of one Mary.
6. Romantic/partner behavior as relationship state, not a cloned persona.

## Near-term product priorities

- Relational Presence & Shared Life
- semantic turn-taking / interruption benchmarking
- ambient desktop-pet surface
- shared-activity UI
- emotional speech delivery mapping
- avatar semantic action protocol
- derived social graph retrieval experiment
- contextual Mary images using approved canonical references
- private vs performer presentation policy

## Deferred until evidence justifies complexity

- replacing the current orchestration stack with Pipecat/LangGraph/etc.
- mandatory graph database
- browser-local WebGPU inference as a Core dependency
- autonomous diary writes directly into canonical memory
- generic computer/shell agent hidden behind a plugin
- VLA/robot policy in Mary Core
- additional cloud services required for startup
