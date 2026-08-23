# Local Presence WebSocket — MaryV2 12.11

12.11 adds an optional loopback WebSocket transport as a foundation for future phone/browser/secondary-screen clients.

## Security posture

- Disabled by default.
- Binds to `127.0.0.1` by default.
- Read-only protocol in this milestone.
- Optional bearer token.
- Exposes bounded display-safe snapshots and ephemeral turn/presence events.
- Does not accept creator instructions, tool approvals, memory writes, or authority-changing commands.

## Configuration

```env
MARY_WEBSOCKET_ENABLED=true
MARY_WEBSOCKET_HOST=127.0.0.1
MARY_WEBSOCKET_PORT=8765
# MARY_WEBSOCKET_TOKEN=<private random token>
```

Do not bind to a LAN/public interface until authentication, authorization, TLS/reverse-proxy strategy, and remote-client threat boundaries are explicitly designed and tested.
