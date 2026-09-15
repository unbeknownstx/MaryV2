# macOS Home Capability Node

The canonical macOS home node exposes the same bounded Mary capability-host contract as Windows while Mary Core remains the only identity/state authority.

## One-time permissions

Enable only the local inference lanes this Mac should execute:

```bash
.venv/bin/python -m scripts.node_permissions allow llm.local
.venv/bin/python -m scripts.node_permissions allow llm.ollama
```

Other capabilities remain default-deny.

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

Local-first voice on macOS is now: configured Piper, then built-in macOS `say` + `afconvert`, then an optional cloud fallback only when configured. Set `MARY_MACOS_TTS_VOICE` to choose an installed system voice.

## Verification

```bash
bash scripts/setup_macos.sh
.venv/bin/python -m scripts.platform_readiness --strict
.venv/bin/python -m scripts.check_local_model_roles
```

The Mac setup script runs the same repository-structure, one-Mary convergence, character/conversation regression, full deterministic suite, offline release gate, and standalone-readiness stages as Windows.

Metal throughput, installed model availability, microphone permission, and external services still require physical-Mac testing.
