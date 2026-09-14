# Live Resource Awareness 13.40

MaryV2 13.40 adds bounded, best-effort resource telemetry for replaceable compute nodes. The goal is to let the existing resource broker make better placement and handoff decisions from measured facts without turning hardware discovery into a startup dependency or execution authority.

## Design rules

- Mary Core remains the only identity/state authority.
- Resource telemetry is operational evidence only.
- Probe commands are fixed by code; no arbitrary shell or user-supplied command is executed.
- Vendor probes have short timeouts and soft-fail when tooling is missing.
- Missing resource measurements never make a node fail registration.
- Apple Silicon unified memory is not mislabeled as dedicated VRAM.
- A resource observation never grants permission to run a workload, unload a model, or mutate the host.

## `mary.distributed.resource_probe`

`observe_live_resources()` reports bounded RAM/GPU observations. It prefers measured vendor information and degrades to weaker hints:

1. NVIDIA `nvidia-smi`: GPU label, total VRAM, live free VRAM.
2. AMD ROCm `rocm-smi`: product information plus total/used VRAM when exposed by the installed tool.
3. Windows `Win32_VideoController`: adapter name and total-memory hint only. This source intentionally does not invent free VRAM.
4. `MARY_NODE_GPU_LABEL` / `MARY_NODE_GPU_MEMORY_GIB`: explicit configured hint when no live probe succeeds.

The result records the source of each observation so later routing can distinguish a live measurement from a configured hint.

## System memory

The probe uses platform-native, dependency-free sources where possible:

- Windows `GlobalMemoryStatusEx`;
- Linux `/proc/meminfo`;
- macOS `sysctl` and `vm_stat` with short timeouts.

RAM and VRAM remain separate fields. On Apple Silicon, system/unified memory remains RAM evidence and is not copied into a fake dedicated-VRAM value.

## Resource broker integration

`resource_snapshot(node_id)` converts the live observation into the existing `ResourceSnapshot` used by 13.37 `plan_resource_handoff()`. This means the broker can distinguish:

- an incoming workload that fits current free VRAM;
- a workload that fits only after releasing a resident warm model;
- a workload that exceeds total measured VRAM;
- an unknown case where eviction must not happen on a guess.

The broker still returns a plan only. It does not unload anything.

## Node advertisement

`runtime.resource_profile` now includes sanitized live fields when available:

- `memory_free_gib`;
- `gpu_label_live`;
- `gpu_backend`;
- `gpu_resource_source`;
- `gpu_memory_gib_live`;
- `gpu_memory_free_gib`;
- `apple_unified_memory`.

These are capability metadata, not permissions. Existing node enrollment, local permission files, typed task channels, and tool approval boundaries remain unchanged.

## Why this matters for Mary's current hardware philosophy

Mary is designed around heterogeneous replaceable workers rather than one oversized GPU. The resource layer therefore needs to answer practical questions such as "does this task fit on the current PC without evicting Ollama?" or "should a future 24 GB node take this image/video workload while another node keeps conversation resident?" using measured evidence instead of model-name or GPU-name assumptions.

13.40 supplies that evidence without binding Mary to NVIDIA, ROCm, a particular model runtime, or a particular future machine.
