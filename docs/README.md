# MaryV2 Documentation Map

The repository contains years of iterative design notes. This file defines where **current authority** lives so active engineering is not driven by an old patch note or release package.

## Start here

- [`../README.md`](../README.md) — current product overview and run/verification entry points.
- [`../MARY_ROOT.md`](../MARY_ROOT.md) — one-Mary authority and persistence contract.
- [`architecture/SYSTEM_REGISTRY.md`](architecture/SYSTEM_REGISTRY.md) — canonical subsystem ownership/status map.
- [`../AGENTS.md`](../AGENTS.md) — contributor/coding-agent constraints.
- [`architecture/PRODUCT_EXPERIENCE_13_7.md`](architecture/PRODUCT_EXPERIENCE_13_7.md) — current product experience/research convergence.
- [`design/MARY_VISUAL_SYSTEM.md`](design/MARY_VISUAL_SYSTEM.md) — cross-platform visual/presentation language.

## Architecture

`docs/architecture/` contains active ownership, data-flow, capability, runtime and security-boundary documentation. When an architecture note conflicts with executable code/tests or `MARY_ROOT.md`, fix the note rather than treating documentation as a second runtime authority.

Important maps include:

- `SYSTEM_REGISTRY.md` — system owners and current status.
- `data_flow.md` — high-level flow between Mary, capabilities and surfaces.
- `RUNTIME_AUTHORITY.md` — Core/surface lifecycle and authority.
- `MCP_CAPABILITY_FABRIC_13_4.md` — optional MCP capability-node boundary.
- `OPENHANDS_WORKER_BOUNDARY_13_4.md` — separate software-engineering worker boundary.
- `NEURO_PATTERN_ADOPTION_13_6.md` — realtime/performer architecture convergence.

## Operations

`docs/operations/` is for current setup, lifecycle, enrollment, platform-readiness and host-operation material. Operational notes should describe the current source tree, not require users to copy old overlay ZIPs into it.

## Design and product experience

`docs/design/` describes shared presentation language across Desktop, SwiftUI and PWA. UI is a projection of Mary state; it does not become an identity or memory owner.

## Research

Current research that materially affects architecture should be summarized into an active architecture/design decision document with explicit adoption/defer/reject status. Raw experiments and dated source surveys belong under research/history instead of remaining as competing instructions.

## History

`docs/history/` preserves superseded implementation plans, prompts, package notes, release reports and project archaeology. Keep it for provenance, but do not use it as current instructions unless the active registry explicitly points back to it.

## Documentation hygiene rule

A current document should answer at least one of these questions:

1. What is MaryV2 now?
2. Who owns this state/capability?
3. How do I operate or test it now?
4. What product/design contract must current surfaces follow?

If it only explains how to apply an old patch, reports an obsolete test count, or describes a replaced architecture, archive it under history or remove it from the active root. Git history already preserves the original text.
