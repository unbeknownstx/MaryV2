# MaryV2 — Next Mac Steps

This sequence assumes the upgraded project is unpacked on the Mac and the repository's private `.env` / persistent Mary data are restored through the existing canonical configuration rather than copied into source-control archives.

## 1. Enter the project and verify source

```bash
cd /path/to/MaryV2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m scripts.run_release_verification
```

Expected checkpoint from this package:

```text
1602 passed, 1 skipped
Release verification PASSED
```

## 2. Rebuild the desktop frontend on the Mac

```bash
cd desktop
npm ci
npm run check
npm run build
cd ..
```

Do this on the host before macOS app packaging. Do not commit `node_modules`.

## 3. Install the useful small local runtime stack

Review options first:

```bash
./scripts/bootstrap_mac_character_runtime.sh --help
```

Recommended first pass:

```bash
./scripts/bootstrap_mac_character_runtime.sh --all
```

This installs/uses local runtimes and fetches the small reviewed Fast Brain / STT / VAD assets into Mary's platform-local model directory, not the Git repository.

Optional roleplay/adapter experiment:

```bash
./scripts/bootstrap_mac_character_runtime.sh --download-roleplay-lab
```

That path is intentionally optional because the adapter requires its exact compatible base model.

## 4. Start a local llama.cpp server when desired

Use the model path printed by the bootstrap/fetch scripts. Example shape:

```bash
llama-server -m "/path/to/local/model.gguf" --host 127.0.0.1 --port 8081
```

Configure the existing Mary llama.cpp provider/device environment to point at that server. Keep the normal cloud-first route unless intentionally testing a local role.

## 5. Allow the Mac node to contribute local LLM capability

```bash
python -m scripts.node_permissions allow llm.llama_cpp
python -m scripts.run_capability_node --enroll-only
python -m scripts.run_capability_node
```

The Mac remains a capability node. Railway/Core remains canonical Mary.

## 6. Optional foreground presence

Run the existing Mac presence reporter if desired. It contributes bounded active-app/window context only; it does not become identity or memory authority.

macOS may request Accessibility permission for front-window metadata.

## 7. Optional World Pulse

Single refresh:

```bash
python -m scripts.refresh_world_context
```

Foreground watch mode:

```bash
python -m scripts.refresh_world_context --watch
```

Current public RSS fallback is optional/disposable world context, not canonical knowledge or Mary memory.

## 8. Optional Twitch / OBS integration

Install optional streaming transport dependency:

```bash
python -m pip install -r requirements-streaming.txt
```

Then configure the documented environment values in `.env` and use:

```bash
python -m scripts.run_twitch_chat_adapter
python -m scripts.run_obs_presence_adapter
```

These adapters normalize external events and forward them to Mary Core. They do not contain a second cognition loop.

## 9. Verify again after host-specific setup

```bash
python -m pytest -q
python -m scripts.run_release_verification
```

Never merge/push a host-specific integration that breaks the canonical release gate.
## 10. New synthesis checks to exercise on real hardware

The deterministic gate proves wiring, not experiential quality. On the Mac, explicitly test:

- `Why Mary Did That` on desktop and mobile after attention/floor events;
- unconfirmed VAD noise does **not** interrupt Mary, while confirmed creator speech does;
- streaming/direct mentions wait when the creator owns the floor;
- the desktop body visibly changes for semantic motion cues such as explain/shrug/teasing/listening;
- node routing reports local capabilities as ready/degraded/unavailable truthfully;
- cross-surface `elsewhere, just now` context appears without copying private raw text;
- Adapter Lab model/LoRA runs remain isolated from canonical memory/relationship/canon.

For a reproducible local model/LoRA matrix, use:

```bash
python -m scripts.run_local_model_matrix --help
```

Start with base-only and low LoRA scales before testing stronger adapter influence. Creator blind review remains the Mary-fit authority.
