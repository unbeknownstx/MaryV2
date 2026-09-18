# macOS Home Capability Node

The canonical macOS home node exposes the same bounded Mary capability-host contract as Windows while Mary Core remains the only identity/state authority.

## Physical M1 / Monterey compatibility

The current creator Mac is an Apple Silicon machine on macOS 12 Monterey, so the Mac host intentionally uses platform-compatible dependency versions instead of blindly copying the Windows toolchain versions.

- Mary source, Core protocol, memory/relationship behavior, desktop frontend, capability fabric, local-model roles, permissions, node broker, VRM/art assets, runtime supervisor, and verification stages remain the same architecture as Windows.
- macOS uses Python 3.10-3.13 for Desktop. Python 3.13 is recommended.
- `requirements-desktop.txt` selects PySide6 6.9.3 on macOS because that line provides a macOS 12 universal2 wheel. Windows/Linux remain on PySide6 6.11.1.
- Node 22.12+ is the preferred frontend runtime on Monterey. The setup script rejects a Node 24 binary line on pre-13.5 macOS because current official Node 24 macOS binaries target newer systems.
- The host adapter is native: Apple Silicon/Metal instead of the Windows RX 580 profile, `say`/`afconvert` instead of Windows SAPI, and a LaunchAgent instead of a Scheduled Task.

Those host-specific substitutions are parity adapters, not separate Mary implementations.

## One-time permissions

Enable only the local inference lanes this Mac should execute:

```bash
.venv/bin/python -m scripts.node_permissions allow llm.local
.venv/bin/python -m scripts.node_permissions allow llm.ollama
```

Other capabilities remain default-deny.

### Optional bounded engineering worker

The Mac can use the same local model as a replaceable coding worker while Core
remains Mary's only identity/state authority:

```bash
.venv/bin/python -m scripts.node_permissions allow engineering.repo.inspect
.venv/bin/python -m scripts.node_permissions allow engineering.repair.plan
.venv/bin/python -m scripts.node_permissions allow engineering.patch.propose
.venv/bin/python -m scripts.node_permissions allow engineering.git.status
.venv/bin/python -m scripts.node_permissions allow engineering.git.diff
.venv/bin/python -m scripts.node_permissions allow engineering.structure.verify
.venv/bin/python -m scripts.node_permissions allow engineering.tests.targeted
```

Repository mutation remains a separate opt-in:

```bash
.venv/bin/python -m scripts.node_permissions allow engineering.repo.apply
```

Tests run in disposable copied workspaces and no generic shell, commit, push, merge or
deploy task exists. See `docs/architecture/ENGINEERING_WORKER_CURRENT.md`.

## Launch

```bash
bash scripts/launch_home_node_macos.sh
```

The launcher uses the same `scripts.run_home_node` implementation as Windows, the same durable enrollment and task broker, and the same benchmark-profile path at `~/.maryv2/node_benchmark_13_11.json`. Apple Silicon defaults to the bounded `mac-apple-silicon` profile.

If Ollama is installed but not reachable, the launcher may start `ollama serve`. Disable that with `MARY_NODE_START_OLLAMA=false`. It never downloads models.

## Start automatically at login

Windows uses a Scheduled Task; macOS uses the equivalent user-level LaunchAgent. It runs as the logged-in user, never as root, and invokes the same canonical home-node launcher:

```bash
bash scripts/install_macos_node_agent.sh
```

Remove it with:

```bash
bash scripts/uninstall_macos_node_agent.sh
```

The generated plist contains only executable/log paths and the MaryV2 label. Credentials remain in Mary's normal private environment/config path and are not copied into launchd configuration.

## Desktop and voice parity

Normal Mac Desktop startup uses the same `mary.desktop.runtime_supervisor` as Windows for LM Studio/Ollama/llama.cpp discovery and bounded `llm.local` hosting.

Local-first voice on macOS is: configured Piper, then built-in macOS `say` + `afconvert`, then an optional cloud fallback only when configured. Set `MARY_MACOS_TTS_VOICE` to choose an installed system voice.

## Verification

```bash
bash scripts/setup_macos.sh
.venv/bin/python -m scripts.platform_readiness --strict
.venv/bin/python -m scripts.check_local_model_roles
```

The Mac setup script runs the same repository-structure, one-Mary convergence, character/conversation regression, full deterministic suite, offline release gate, and standalone-readiness stages as Windows. CI also installs the Mac desktop Qt dependencies under Python 3.13, performs a Qt import smoke test, and builds the same Vite desktop under Node 22.

Metal throughput, installed model availability, microphone permission, local Ollama/LM Studio services, and external providers still require physical-Mac testing.
