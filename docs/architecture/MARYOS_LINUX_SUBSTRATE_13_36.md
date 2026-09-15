# MaryV2 13.36 — MaryOS Linux Substrate

## Decision

MaryOS is a Linux operating environment around the existing one-Mary architecture, not a new kernel and not a model-owned OS. Arch/Omarchy is the preferred experimental desktop target because Hyprland/Quickshell is programmable, but **Omarchy is not a Core dependency**. Windows, macOS, iPhone/PWA and ordinary Linux remain valid surfaces/nodes.

## Placement

```text
Mary Core: identity / memory / relationship / policy
                    |
          capability + model fabrics
                    |
           MaryOS host boundary
      +-------------+--------------+
      |             |              |
 read-only OS   typed future   presentation
 projection      OS actions      shell/UI
      |             |              |
             systemd / Linux
                    |
                  hardware
```

MaryOS extends the host/node layer. It does not move Mary identity into Linux, a desktop shell, a local model or a machine record.

## 13.36 implementation

`mary.distributed.os_environment` reports sanitized distro, systemd, desktop/display, Hyprland, Quickshell, Omarchy and package-manager presence without subprocess execution or mutation. `scripts.run_home_node` folds a bounded subset into the existing private `runtime.resource_profile`.

The systemd template runs the existing bounded home node as a user service. Enabling it is explicit.

13.36 intentionally adds **no OS mutation executor**. Future OS actions must be typed and reuse the existing device permission model. Generic shell text, sudo, arbitrary argv, arbitrary writes, bootloader changes and automatic package installation are out of scope.

## Future layers

### 13.37 candidate — Mary Shell

Build a Quickshell/Hyprland surface for Mary presence, workspaces, current project, voice state, node health and approved actions. It remains presentation/control UI over Core.

### Later — typed OS actions

Add narrow service/app/session/package proposals with schemas, allowlists, audit results and creator approval. No generic terminal tool.

### Later — reproducible MaryOS image

After real Linux-node validation, freeze the package/config/service contract and produce a reproducible Arch/Omarchy-derived installer/ISO. Disk and bootloader operations remain explicit installer concerns, never model autonomy.

## Hardware strategy

MaryOS improves utilization of whatever host exists. The model execution fabric continues selecting among Ollama/llama.cpp, Mac/PC/Linux nodes and cloud/frontier providers using measured feasibility. A future CUDA workstation is another node, not another Mary.
