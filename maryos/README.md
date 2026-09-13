# MaryOS

MaryOS is the Linux operating-environment layer for MaryV2. It is **not** a second Mary, a model-as-kernel experiment, or a grant of unrestricted shell/root authority.

The near-term target is an Arch/Omarchy-class Linux host where Linux owns the kernel/drivers/processes/devices, Mary Core remains canonical identity/state authority, the existing capability fabric owns replaceable execution, and OS changes become typed permission-bounded actions rather than model-generated shell commands.

## Current 13.36 foundation

Implemented now:

- `mary.distributed.os_environment.MaryOSEnvironmentProfile`;
- `python -m scripts.maryos_status` read-only readiness inspection;
- Linux host metadata in the home node's `runtime.resource_profile`;
- a hardened systemd user-service template for `scripts.run_home_node`;
- an installer that never uses sudo and only enables the service with explicit `--enable`;
- architecture/security/boot contracts and deterministic tests.

Not implemented yet: Mary desktop replacement, Quickshell/Hyprland UI, package/service mutation tools, root actions, custom ISO, disk installation or partitioning.
