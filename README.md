# MaryV2

**Many surfaces. Many capability nodes. One persistent Mary.**

MaryV2 is a local-first, cloud-capable persistent character runtime. Mary is not a wrapper around one language model: identity, authored character evidence, relationship continuity, memory, developed self, agency, expression, permissions, realtime coordination, tools, and capability routing have explicit owners. Models, speech engines, devices, creative services, and user interfaces are replaceable capabilities beneath that runtime.

Current architecture line: **13.7 product/experience hardening** (built on the green 13.6 convergence baseline).

## What is in the repository

- **Canonical Core** — one long-lived `MaryApplication` owned remotely by `MaryCoreService` when `MARY_CORE_URL` is configured.
- **Character + continuity** — authored CharacterSourcebook material, canonical biography, relationship state, episodic/semantic/working memory, developed preferences, growth, grounded experience and agency.
- **Provider router** — cloud/free-first and private/local routes with Ollama/llama.cpp support; paid specialist routes remain explicit.
- **Realtime interaction** — attention arbitration, VAD/barge-in contracts, interruptible presentation sessions, incremental text segmentation and sentence-oriented TTS primitives.
- **Capability fabric** — enrolled Windows/macOS/Linux nodes, typed tasks, MCP adapters, per-tool/device permission boundaries, diagnostics and optional local model execution.
- **Creator surfaces** — desktop, native SwiftUI iPhone, mobile/PWA and terminal, all projecting the same Mary rather than constructing separate identities.
- **Performer/creative surfaces** — bounded Twitch/OBS contracts, avatar/VRM presentation, Studio/project tooling, perception, browser context, game-intent routing and media/creative capability discovery.

## Authority model

Read these before changing architecture:

1. [`MARY_ROOT.md`](MARY_ROOT.md) — human-readable root contract.
2. [`docs/architecture/SYSTEM_REGISTRY.md`](docs/architecture/SYSTEM_REGISTRY.md) — current subsystem/owner map.
3. [`AGENTS.md`](AGENTS.md) — engineering constraints for contributors and coding agents.
4. [`docs/README.md`](docs/README.md) — documentation map.

Historical documents under `docs/history/` are project archaeology. They never override current code, tests, `MARY_ROOT.md`, or the System Registry.

## Quick start

### Python environment

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Optional host/UI dependencies are intentionally separate so Mary Core does not require desktop, MCP, local-model, or voice extras merely to start.

### Run a local/standalone development Mary

```bash
python -m scripts.run_mary
```

### Run the canonical remote Core

Configure the required environment in your host, then use the repository's Core/server launcher. Surfaces with `MARY_CORE_URL` configured must connect to that Core and **must not** construct another Mary.

### Desktop

```bash
# macOS
bash scripts/launch_macos.sh

# Windows
python -m scripts.run_desktop
```

The desktop treats 3D/VRM rendering as presentation, not a startup dependency. macOS can use the portrait-safe renderer path when WebGL/Metal is unavailable.

### Native iPhone

The long-term native client is under [`ios/MaryV2iOS/`](ios/MaryV2iOS/). Generate/open the Xcode project on macOS, select your signing team, and run on device or simulator. Provider credentials remain on Core; the app stores its Core credential in Keychain.

### Mobile/PWA

`mobile_web/` is the compatibility/prototype web surface and can be served through Mary's mobile server. `mobile_native/` remains a compatibility wrapper while native SwiftUI is the preferred iPhone client.

## Local models and nodes

Ollama and llama.cpp are optional private/local capabilities. A machine can enroll as a capability node without becoming Mary or owning identity/state. Node discovery does not imply execution permission; device-local policy and Core authorization still apply.

MCP integrations are similarly optional and lazy. External services are never Core startup dependencies and arbitrary shell execution is intentionally excluded from the capability fabric.

## Character material

Approved creator-authored material belongs in:

```text
character_sources/active/
```

Draft/unapproved material belongs in `character_sources/drafts/`. Fictional canon (`[FC]`) is reference material and is not automatically AI Mary's lived memory.

## State and secrets

Repository source is not Mary's mutable identity/state store. Runtime state uses host-native application storage or explicit `MARY_DATA_DIR`. Do not commit `.env`, provider keys, device credentials, runtime state, generated caches, `node_modules`, model weights, or restored historical `data/` folders.

## Verification

Fast structural check:

```bash
python -m scripts.verify_repository_structure
```

Full deterministic suite:

```bash
python -m pytest -q
```

CI also checks desktop production builds, platform contracts and native iPhone project/build readiness. Optional providers may be unavailable without making the canonical architecture unhealthy.

## Product direction

MaryV2 is the demanding reference implementation for a broader persistent-instance architecture: continuity should survive model changes, devices should contribute capabilities without stealing authority, public/private surfaces should remain projections of one identity, and the experience should degrade gracefully when optional services disappear.

The current product polish/research plan is documented in [`docs/architecture/PRODUCT_EXPERIENCE_13_7.md`](docs/architecture/PRODUCT_EXPERIENCE_13_7.md).
