# MaryV2 development plan after 12.12.2

1. Install 12.12.2 on the canonical Windows host and run the normal conversation set again.
2. Compare the new trace stages. The key question is whether the old ~1.05 second fixed gap lived in QWebChannel payload transfer, browser audio readiness, or playback scheduling.
3. Listen specifically for restraint: Mary should sound conversational most of the time, with stronger acting reserved for real excitement, concern, conflict, amusement, etc.
4. Pull the minimal local model tier (`qwen3:1.7b`, `llama3.2:1b`, `gemma3:1b`) and run the Local Model Lab. Do not promote anything automatically.
5. If useful, run the extended tier (`smollm2:1.7b`, `llama3.2:3b`) and reasoning specialist (`phi4-mini`). Keep `qwen3:4b` as the known Mary-like quality baseline.
6. Use the explicit Voice Lab to compare the current ElevenLabs voice with alternate voice IDs under the same restrained settings before deciding the voice itself is wrong.
7. Once local/model/voice measurements are stable, prototype sentence/chunk streaming behind the same provenance/reflection boundary so speech can begin before a long generated response is complete.
8. Continue character-performance work with subtle gaze, body timing, emotional inertia and idle behavior. Expression should support dialogue rather than advertise itself.
9. Use Codex directly in the canonical VS Code workspace for iterative code work, with `AGENTS.md` boundaries and the VS Code test tasks.
10. When the RTX 3090 arrives, benchmark larger local language, TTS, STT and vision engines behind the same interfaces instead of redesigning Mary around the GPU.

## Hybrid dialogue benchmark next step

Run the benchmark-only hybrid matrix on the canonical Windows host, review the
preserved deterministic/1.7B/4B samples by response class, and repeat the
low-risk social cases across more turns to measure repetition and p95 latency.
Keep precision answers in the typed local composer, keep open/thinking work on
their existing classes, and do not promote or route any local model until the
human review and repeated measurements support a separate explicit decision.
