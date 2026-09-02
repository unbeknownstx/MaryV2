# Mac Character Runtime — first boot

This phase preserves the same canonical Mary Core. The Mac is a client/capability node, not a second Mary.

## 1. Establish the source baseline

```bash
git status
git fetch origin
git checkout main
git pull --ff-only
python -m pytest -q
python -m scripts.run_release_verification
```

If the source is being applied from the September 1 upgrade ZIP rather than Git, make a copy of the existing folder first and compare the included upgrade manifest.

## 2. Boot Mary normally first

Do not enable local models yet. Verify:

- the desktop resolves to canonical remote Core when Core is configured;
- Mary’s existing state/character/sourcebook loads;
- mobile/web remains a thin client;
- no `data/` migration is triggered merely by this upgrade.

## 3. Inspect character-runtime state

The canonical Core now exposes typed actions for:

- `presence.scene.status`
- `stream.status`
- `world.status`
- `world.refresh_plan`
- `model.adapter.status`
- `realtime.speech_request`

These are the same Core-owned views regardless of client.

## 4. Optional local Apple-Silicon lane

A local model is optional. Mary remains cloud-first unless explicitly changed.

One current llama.cpp installation option on macOS is:

```bash
brew install llama.cpp
```

Then:

```bash
./scripts/run_llama_cpp_mac.sh
```

That script defaults to the reviewed `Qwen3-1.7B Q4_K_M` candidate. It may download the model through llama.cpp/Hugging Face when explicitly launched.

In another shell, opt Mary into the provider for a test only:

```bash
export MARY_LLAMA_CPP_ENABLED=true
export MARY_LLAMA_CPP_BASE_URL=http://127.0.0.1:8080
```

Use an explicit provider/session override first. Do not reorder the stable default provider route until latency/quality is measured.

## 5. Optional roleplay LoRA lab

List reviewed assets:

```bash
python -m scripts.fetch_model_candidate --list
```

Fetch the exact compatible base and adapter only if you want to run the experiment:

```bash
python -m scripts.fetch_model_candidate qwen3-4b-heretic-q4km-roleplay-base --download
python -m scripts.fetch_model_candidate rockerboo-qwen3-4b-roleplay-lora-f16 --download
./scripts/run_roleplay_adapter_lab_mac.sh
```

Start with a low adapter scale in Mary’s requests, for example:

```bash
export MARY_LLAMA_CPP_ENABLED=true
export MARY_LLAMA_CPP_LORA_SCALES='[{"id":0,"scale":0.25}]'
```

Then compare `0.0`, `0.25`, `0.5`, etc. against the same held-out Mary evaluation prompts. A generic roleplay adapter is never promoted merely because it is expressive.

## 6. Optional local speech

The desktop STT adapter supports `whisper_cpp` as an optional provider. Point it at a `whisper-cli` executable and a local ggml Whisper model:

```bash
export MARY_STT_PROVIDER=whisper_cpp
export MARY_WHISPER_CPP_EXECUTABLE=/opt/homebrew/bin/whisper-cli
export MARY_WHISPER_CPP_MODEL=/path/to/ggml-base.en.bin
```

Silero/sherpa-onnx VAD remains an explicit optional asset for continuous turn detection. It is not required for normal Mary chat.

## 7. What stays shared vs device-local

### Core/shared
- identity and character
- relationship/developed self
- canonical memory
- Live Scene projection
- current World Context
- streaming social state
- autonomy policy
- adapter-lab evaluations/configuration

### Device-local capabilities
- foreground-window sensing
- local microphone capture
- local STT/TTS engines
- llama.cpp/Ollama
- filesystem/application control
- local GPU/CPU capabilities

A client that lacks a local capability should ask Core/node routing for an available node rather than creating another Mary.
## 8. Second-synthesis runtime additions

The current package also contains:

- shared realtime/stream `SpeakerScheduler`;
- safe `RealtimeDecisionTrace` projected to desktop/mobile as **Why Mary Did That**;
- confirmed-VAD barge-in gating;
- readiness-aware capability routing;
- bounded cross-surface stage awareness;
- dynamic valid-action windows;
- semantic motion cues that the current desktop VRM now physically consumes;
- blinded/reproducible Adapter Lab model/LoRA evaluation.

These features do not require enabling a local model to preserve normal Mary behavior. Test them first with the stable provider route, then layer local models/LoRAs onto the same Core.
