---
name: Railway SSH key discovery
description: Environment-specific key discovery behavior when using Railway CLI SSH for protected volume exports.
---

Railway CLI SSH key registration selects from keys it discovers through the
SSH agent or under `~/.ssh`. In this environment, passing a key located only
under `/tmp` to the key-selection option still reported that no local SSH keys
were available.

**Why:** A protected production-volume export failed repeatedly before transfer
because the CLI help implied that an arbitrary key path was sufficient.

**How to apply:** Generate a temporary one-purpose key under `~/.ssh`, register
that discovered key, run Railway SSH commands from the already-linked project
directory, then remove the key from Railway and securely erase both local key
files immediately after the transfer.