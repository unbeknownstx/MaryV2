# MaryV2 current state — 12.12.2

MaryV2 12.12.2 keeps the 12.12 Cognitive Reservoir/Character Runtime and calibrates the part users feel most immediately: ordinary back-and-forth.

## Proven architecture

- Local Mind/Reservoir can answer represented reflex/state turns in single-digit to low-double-digit milliseconds before TTS on the live Windows host.
- Open language can escalate to the fast Groq conversation route; hard tasks still retain thinking/tool/expert routes.
- ElevenLabs Flash is fast enough to remain the current premium/reference voice while local voice alternatives are evaluated separately.
- The VRM, TTS and GUI are presentation containers over the same canonical Mary runtime.

## 12.12.2 changes

- **Natural Conversation Director** — ordinary speech now anchors to a restrained baseline. Emotion is blended in with low gain instead of swapping Mary into a theatrical profile each turn.
- **Dialogue direction** — model prompts explicitly say Mary should simply talk rather than perform; normal conversation is usually 1–4 sentences and token budgets are ceilings.
- **TTS text calibration** — stacked punctuation/long ellipses are reduced before speech because they are strong performance cues.
- **Fast Audio Transport** — synthesized audio is staged into a bounded temporary file cache so the browser can receive a file URL instead of a large base64 blob through QWebChannel.
- **Playback trace** — text-ready, UI-payload, audio-ready, play-request and perceived-start timings are separately measurable.
- **Local Model Lab v2** — compares qwen3:1.7b, llama3.2:1b, gemma3:1b, smollm2:1.7b, llama3.2:3b, phi4-mini and the existing qwen3:4b baseline by latency, basic character hygiene and restraint.
- **Hybrid Dialogue Runtime lab** — adds a benchmark-only deterministic
  authority/risk classifier and typed procedural LocalComposer V2. qwen3:1.7b
  is an invisible shadow only for strictly low-risk social turns by default;
  precision, open conversation, and thinking remain separate classes. Nothing
  is connected to production routing and no model is promoted.
- **Voice Lab** — explicit A/B pack generation for the current/alternate ElevenLabs voices; zero network calls unless `--synthesize` is requested.
- **Codex/VS Code workflow** — repository instructions plus VS Code tasks for fast/full/release/model-lab work against the canonical workspace.

## Safety / state

The Cognitive Reservoir remains derived and rebuildable. The audio cache and runtime reports are ephemeral presentation/developer artifacts. None of them are Mary memory. Hybrid shadow candidates are never displayed, spoken, or written into Mary state. `.env` and real persistent data remain outside test/release payloads.
