# MaryV2 13.14 — Character Intelligence & Learning Interop

13.14 integrates the strongest ideas found in current character-memory, agent-evaluation, prompt-optimization, local-audio, multimodal and training projects without replacing Mary's existing authority graph.

## What already existed

Mary already had more than a flat persona prompt:

- `CharacterSourcebook` with bounded per-turn creator-evidence retrieval;
- evidence labels separating fictional canon, shared DNA, AI Mary, public performer, alternate and negative examples;
- `TurnMindState` projection into every canonical turn;
- `MaryEvaluationSet` deterministic character acceptance cases;
- adapter lab/runner, experiments, grounding, feedback and learning systems;
- turn observability and provider/node routing.

13.14 therefore does **not** add a second memory database or another agent framework.

## Structured character intelligence

The canonical `from mary.character import CharacterSourcebook` now resolves to a drop-in enriched sourcebook. It keeps the existing deterministic retrieval algorithm but enriches each selected prompt view with:

- typed character claims;
- explicit authority tiers;
- record/content hashes;
- provenance edges from Mary -> evidence;
- fictional/negative evidence boundaries;
- bounded positive-vs-negative authored-evidence collision diagnostics.

This is a Graphiti-style *projection* of creator evidence, not a Graphiti-owned truth store. No model output can mutate it. Fictional canon remains reference rather than lived AI memory.

## MaryBench interoperability

`mary.learning.interop` converts the existing `MaryEvaluationSet` into a portable experiment bundle containing:

- generic MaryBench records;
- DSPy-style examples;
- Promptfoo-style test objects;
- Phoenix-style dataset rows.

Run:

```text
python -m scripts.export_marybench
```

The default output is outside the repository under `~/.maryv2/labs/`.

External optimizers may produce `OptimizationProposal` artifacts. Their status is always `proposal_only`; optimizer output does not modify Mary prompts, identity, sourcebook, memory or relationship state automatically. A candidate must be benchmarked and deliberately promoted through Mary's normal configuration/code-review process.

## Specialist backend catalog

`mary.distributed.specialist_catalog` gives research-derived optional tools one vocabulary and explicit authority boundary:

| Backend | Intended role | Mary authority |
| --- | --- | --- |
| FluidAudio | Apple STT/VAD/diarization | sensor only |
| Qwen3-ASR | local multilingual STT | sensor only |
| TEN VAD | low-latency VAD | sensor only |
| Chatterbox | expressive TTS | presentation only |
| llama.cpp mtmd | local multimodal perception | sensor only |
| OmniParser | screenshot/UI semantics | sensor only |
| Graphiti | temporal graph projection | projection only |
| DSPy/GEPA | prompt/program optimization lab | proposal only |
| Phoenix | traces/evaluation datasets | evaluation only |
| Promptfoo | behavioral regression/red-team | evaluation only |
| Unsloth/Axolotl | future local adaptation | proposal only |

Run:

```text
python -m scripts.check_specialist_backends
```

The diagnostic reports module/executable/configured-endpoint presence only. It never prints secrets and none of these tools become a Mary Core startup dependency.

## Specialist STT bridge

The existing `DesktopSpeechToText` adapter now accepts three additional **device-configured** modes while preserving Groq, faster-whisper and whisper.cpp:

- `MARY_STT_PROVIDER=qwen3_asr` with `MARY_QWEN_ASR_ENDPOINT`;
- `MARY_STT_PROVIDER=fluid_audio` with `MARY_FLUID_AUDIO_ENDPOINT`;
- `MARY_STT_PROVIDER=specialist_http` with `MARY_STT_ENDPOINT`.

Only HTTPS or loopback HTTP endpoints are accepted. Capability tasks cannot choose the URL, model path or executable. The same `sensor.audio_transcribe` capability therefore supports these candidates without changing Mary Core or the public creator-voice bridge.

## Semantic screen perception

13.14 adds `sensor.screen_describe`, a third permission-gated home sensor capability. It closes the gap between *capturing* a screenshot and giving Mary a compact semantic observation.

A node may be configured with:

- `MARY_VISION_PROVIDER=llama_cpp_mtmd` + `MARY_LLAMA_CPP_VLM_URL`; or
- `MARY_VISION_PROVIDER=omniparser` + `MARY_OMNIPARSER_ENDPOINT`.

The executor captures one bounded screenshot locally, calls only the preconfigured endpoint, and returns a sanitized description plus optional UI-region labels. Remote tasks may choose only `scene`, `ui`, or `stream` description mode and bounded capture quality/width. They cannot supply a URL, model, filesystem path, mouse/keyboard command, click target or follow-on action.

Visual descriptions remain ephemeral perception evidence. They are not memory truth and do not grant computer-control authority.

## Adoption rule

Research projects are treated as component libraries and experiments, not architectural authorities. A specialist may own temporary computation, but one canonical Mary Core continues to own identity/state; existing MemoryManager/RelationshipManager/TurnMind owners remain intact; proposal-only autonomy remains; device permissions remain; no arbitrary shell/computer control is introduced.

## Next live work

13.14 deliberately establishes contracts before hardware-specific selection. At home, benchmark the actual Mac/Windows nodes and then enable only the specialists that beat existing paths on latency, quality, privacy or cost. The highest-value candidates are Apple audio offload, local multimodal screen description and expressive local TTS. Chatterbox remains catalogued but is intentionally not promoted into the live voice route until it is benchmarked against the existing ElevenLabs/Piper/SAPI stack.
