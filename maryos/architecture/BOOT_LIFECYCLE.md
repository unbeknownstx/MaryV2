# MaryOS Boot Lifecycle

```text
firmware / bootloader
        |
Linux kernel
        |
systemd user session
        |
mary-home-node.service
        |
scripts.run_home_node
        |
durable enrollment + device permissions
        |
Mary Core
        |
bounded capabilities advertised
```

A failed node/model/renderer/sensor/network connection degrades capability rather than erasing Mary.

## 13.36 bring-up

1. Install Linux/Omarchy manually on a dedicated/test disk.
2. Clone MaryV2 and create the Python environment.
3. Configure `~/.config/maryv2/node.env` (including `MARY_CORE_URL`).
4. Run `python -m scripts.maryos_status`.
5. Run `python -m scripts.run_home_node --enroll-only`.
6. Validate the node interactively.
7. Run `maryos/install-user-service.sh`.
8. Only after validation, run `maryos/install-user-service.sh --enable`.

Quickshell/Hyprland desktop integration and custom ISO construction are later phases over the same Core/node boundary.
