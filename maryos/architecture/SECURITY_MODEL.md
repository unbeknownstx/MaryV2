# MaryOS Security Model

MaryOS is a host layer beneath the same canonical Mary Core. Linux retains kernel/process/device/filesystem enforcement; capability discovery never grants permission; the desktop shell never becomes an identity owner.

## No arbitrary root shell

13.36 exposes no generic command, argv, terminal, sudo, package-manager, systemctl or filesystem-mutation capability to model output. Future host actions must be typed and narrow (for example an allowlisted service restart), input-validated, device-permission gated and creator authorized.

## Boot and secrets

The provided unit is a systemd user service running the existing bounded home node with NoNewPrivileges. It does not move Core authority to the machine. Omarchy, Hyprland, Quickshell, Ollama and llama.cpp remain optional capabilities, never Core startup dependencies.

Secrets remain outside Git and use existing platform-native config/state roots. The installer never partitions disks, installs packages, invokes sudo, changes bootloaders or modifies system files.
