# MaryV2 13.5 platform readiness

Mary remains one canonical Core. Mac and Windows hosts are capability surfaces; the native iPhone app is a client surface. Optional local packages never become Core startup dependencies.

## Unified host profile

`requirements-host-extras.txt` collects the optional packages we have added across the recent development passes:

- bounded MCP client support for OpenDesign, Scrapling, and Langflow
- local Whisper STT
- ONNX / sherpa-onnx realtime speech components
- WebSocket stream/presence support

Install this profile only on a Mac or Windows machine intended to provide those capabilities:

```bash
python -m pip install -r requirements-host-extras.txt
```

Mary still boots without any of these packages.

## Readiness report

Run:

```bash
python -m scripts.platform_readiness --strict
```

For machine-readable output:

```bash
python -m scripts.platform_readiness --strict --json
```

The report is read-only. It does not start Ollama, llama.cpp, Piper, MCP servers, or any other process. It reports only executable/package/configuration presence and never prints secret values.

## Mac

Use the existing setup/bootstrap tools, then install host extras when this Mac will act as a full capability node:

```bash
bash scripts/setup_macos.sh
.venv/bin/python -m pip install -r requirements-host-extras.txt
.venv/bin/python -m scripts.platform_readiness --strict
.venv/bin/python -m scripts.mcp_node_diagnostics status
```

Local Ollama and llama.cpp continue to use the existing node/runtime paths. MCP services are configured by URL and exact tool allowlist; Mary never spawns arbitrary MCP subprocesses.

## Windows PC

Use the existing isolated Windows setup, then add the host profile:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements-host-extras.txt
.\.venv\Scripts\python.exe -m scripts.platform_readiness --strict
.\.venv\Scripts\python.exe -m scripts.mcp_node_diagnostics status
```

The PC can then run `scripts\launch_windows_node.ps1` or the optional scheduled logon task already provided by the repository.

## iPhone

The native app remains a Core client. It does not embed Mary identity authority or host MCP/local-model packages. CI regenerates the Xcode project with XcodeGen and compiles the iPhone simulator target on macOS for every readiness PR.

## What CI can verify remotely

GitHub Actions verifies repository structure and readiness contracts on Linux, macOS, and Windows, plus a native iPhone simulator build on macOS. The existing deterministic/convergence workflows continue to cover the full Python suite and broader application checks.

## What still requires the physical machine

The following cannot be truthfully marked live until tested on the actual host/device:

- microphone/speaker permissions and physical audio I/O
- local Ollama/llama.cpp model availability and GPU/Metal performance
- Piper/local voice model files
- external MCP server URLs, credentials, and exact tool allowlists
- iPhone signing, installation, microphone permissions, and physical-device networking
- OBS/Twitch/Unity/VRM integrations that depend on locally running applications

Those are host-level activation checks, not missing Core architecture.

## OpenHands boundary

OpenHands remains a separate sandboxed engineering worker. It is intentionally not installed into Mary Core and is not exposed as `shell`, `exec`, or a generic node capability. See `docs/architecture/OPENHANDS_WORKER_BOUNDARY_13_4.md`.
