# MaryV2 13.4 — bounded MCP capability fabric

This document defines the optional MCP extension for Mary capability nodes.

## Authority rule

MCP does **not** create another Mary and does not move identity, relationship,
memory, developed self, agency, emotion, permissions, or continuity out of the
canonical Mary Core.

The flow is:

```text
creator/surface
    -> canonical Mary Core
    -> existing typed DeviceTaskBroker
    -> enrolled + session-scoped capability node
    -> node-local capability permission
    -> exact MCP server/tool permission
    -> configured Streamable HTTP(S) MCP endpoint
    -> sanitized result
    -> Core as task output/evidence
```

MCP discovery is capability discovery, not authorization. MCP results are task
output/evidence until an existing governed Mary subsystem deliberately accepts
them.

## Supported 13.4 MCP capabilities

| Capability | Purpose | Endpoint |
|---|---|---|
| `mcp.opendesign` | design-system/reference tools | creator-configured OpenDesign MCP URL |
| `mcp.scrapling` | bounded web extraction/scraping tools | creator-configured Scrapling MCP URL |
| `mcp.langflow` | expose selected Langflow flows as MCP tools | creator-configured Langflow MCP URL |

There is intentionally no generic `mcp.*` escape hatch and no dynamic server
name supplied by Core.

## Transport and startup behavior

Mary only acts as an MCP **client** over preconfigured Streamable HTTP(S)
endpoints. Mary does not launch MCP servers, run `npx`, run `uvx`, invoke a
shell, or accept a command/argv from a Core task.

The MCP SDK is optional and node-only:

```bash
python -m pip install -r requirements-node-mcp.txt
```

It is not included by `requirements.txt`. Missing MCP packages or unavailable
MCP services must not prevent Mary Core, Desktop, Mobile, Terminal, Ollama, or
llama.cpp from starting.

## Node-local configuration

No MCP endpoint is enabled by default.

Examples:

```bash
# OpenDesign remote MCP
export MARY_MCP_OPENDESIGN_URL="https://opendesign.cc/mcp/http"

# Scrapling running separately on the same machine
export MARY_MCP_SCRAPLING_URL="http://127.0.0.1:8000/mcp"
export MARY_MCP_SCRAPLING_BEARER_TOKEN="node-local-secret"

# Langflow project MCP server
export MARY_MCP_LANGFLOW_URL="http://127.0.0.1:7860/api/v1/mcp/project/PROJECT_ID/streamable"
export MARY_MCP_LANGFLOW_API_KEY="node-local-secret"
```

Generic headers are also supported per server with
`MARY_MCP_<SERVER>_HEADERS_JSON`. Header values, API keys, bearer tokens, and
full endpoint paths are never advertised to Core.

Plain HTTP is allowed automatically only for loopback endpoints. A non-loopback
HTTP endpoint is rejected unless the node operator explicitly sets
`MARY_MCP_ALLOW_INSECURE_REMOTE=true`. HTTPS is the expected remote transport.

## Double permission gate

Capability permission and tool permission are separate and both default deny.

```bash
python -m scripts.node_permissions allow mcp.opendesign
python -m scripts.node_permissions allow-tool opendesign recommend_references
python -m scripts.node_permissions allow-tool opendesign get_design_system
```

Removing either gate prevents execution:

```bash
python -m scripts.node_permissions deny-tool opendesign get_design_system
python -m scripts.node_permissions deny mcp.opendesign
```

A discovered tool is never auto-added to the allowlist.

## Discovery and diagnostics

Local/config-only status performs no network call:

```bash
python -m scripts.mcp_node_diagnostics status
```

Explicit discovery contacts one configured server and returns only bounded tool
names plus their local allow/deny state:

```bash
python -m scripts.mcp_node_diagnostics discover opendesign
python -m scripts.mcp_node_diagnostics discover scrapling
python -m scripts.mcp_node_diagnostics discover langflow
```

Probe every configured server:

```bash
python -m scripts.mcp_node_diagnostics diagnostics
```

Descriptions and raw schemas are not automatically injected into Mary state.

## Task contract

Core may queue only:

```json
{
  "capability": "mcp.opendesign",
  "intent": "Find references for a clean iPhone companion interface",
  "args": {
    "tool": "recommend_references",
    "arguments": {
      "query": "clean AI companion mobile interface"
    }
  }
}
```

Core cannot supply endpoint URLs, authentication headers, credentials, process
commands, or alternate transports.

## Sanitization

Before enqueue:

- tool names are bounded identifiers;
- arguments must be a JSON object;
- nesting, item counts, strings, and total serialized size are bounded;
- credential-like keys are rejected;
- bearer/JWT/API-key-looking values are rejected.

Before results return to Core:

- secret-like fields are replaced with `[REDACTED]`;
- bearer/JWT/API-key-looking strings are redacted;
- endpoint/auth/header fields are removed from the result envelope;
- result collections and strings are bounded;
- oversized results are deterministically truncated;
- only task output returns; node credentials/configuration do not.

## Existing node security remains authoritative

This extension reuses the current durable enrollment and per-session node token.
It does not change:

- creator-authorized enrollment;
- durable device trust;
- session rotation/isolation;
- stale-node task expiry;
- selected-node-only completion;
- offline/sleep task gating;
- proposal-only autonomy.

## Provider routing remains unchanged

`llm.ollama` and `llm.llama_cpp` retain their existing role/model routing.
The MCP fabric is a sibling capability path, not a replacement LLM router.

## OpenHands boundary

OpenHands is intentionally **not** an MCP capability in this fabric. See
`docs/architecture/OPENHANDS_WORKER_BOUNDARY_13_4.md`. It is designed as a
separate sandboxed software-engineering worker that returns patches/test
evidence and never becomes Mary identity or Core authority.
