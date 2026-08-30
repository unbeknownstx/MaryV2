# Runtime Authority and Topology

## Core rule

A surface never becomes Mary. A capability node never becomes Mary. A model never becomes Mary.

```text
creator
  ↓
Mary surface (Desktop / Mobile / Terminal)
  ↓
canonical Mary Core or explicit standalone MaryApplication
  ↓
Mary cognition/context/state owners
  ↓
capability routing
  ├─ cloud models/services
  ├─ Windows node / Ollama / local files
  ├─ Mac/future nodes
  └─ future rented compute
```

## Remote mode

If `MARY_CORE_URL` is configured, Desktop, Mobile and Terminal must talk to the remote Core and must not instantiate a second local `MaryApplication`.

## Standalone mode

If `MARY_CORE_URL` is intentionally absent, a source/development launch may construct one local `MaryApplication`.

## Node mode

A Windows node can run headlessly and register approved capabilities with Core. This allows an iPhone or other remote surface to request local Ollama work while Mary Desktop is closed, provided the PC, Ollama, node process, permissions and Core connection are available.
