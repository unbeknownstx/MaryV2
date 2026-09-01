---
name: Replit preview authentication boundary
description: Why Replit development identity headers cannot replace Mary Mobile bearer authentication.
---

Keep bearer authentication mandatory for non-loopback Mary Mobile clients.
Do not mint a privileged Mobile session from Replit development headers such as
`X-Replit-User-Id`, even when host and origin checks also pass.

**Why:** Replit development identity headers are not a server-verifiable signed
credential and can be spoofed. The creator explicitly chose not to add Clerk or
another authentication subsystem solely for development-preview convenience.

**How to apply:** Treat automatic secret-free Replit preview bootstrap as a
nonblocking development-experience gap. Revisit only if Replit supplies a
server-verifiable signed development assertion or Mary adopts an already-needed
cryptographically verifiable application session.