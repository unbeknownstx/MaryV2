# MaryV2 Root Authority

Human-readable companion to `mary.runtime.root_authority.MaryRootAuthority`.

## Authority hierarchy

1. **Mary identity / authored character / developed self** — canonical self definition and governed development.
2. **Relationship / memory / experiential continuity** — persistent lived continuity and creator relationship evidence.
3. **Runtime policy / permissions / autonomy** — what Mary may do now and under which bounded authority.
4. **Turn context** — current input, recent conversation, task/project context, relevant retrieval, relevant authored evidence.
5. **Capability fabric** — LLMs, search, files, code, speech, perception, creative services and integrations.
6. **Nodes** — cloud, Windows, Mac, rented compute, future GPU/server hosts.
7. **Surfaces** — desktop, mobile/web, terminal and performer/public interfaces.

## One-Mary resolution

- `MARY_CORE_URL` present: surfaces use remote Core and **must not construct local Mary**.
- `MARY_CORE_URL` absent: explicit standalone development may construct one local `MaryApplication`.
- Capability nodes can run independently of UI surfaces but never become identity/state authority.
- Models/providers are replaceable cognition capabilities; no provider/model is Mary.

## Evidence boundary

Evidence labels:

- `[FC]` fictional canon; never imported as AI Mary's lived memory.
- `[DNA]` creator-authored character evidence.
- `[AI]` developed/lived Mary evidence.
- `[PUB]` public/performance behavior.
- `[ALT]` alternate/experimental interpretation.
- `[NEG]` anti-example.

## Capability rule

Capability is not authority and discovery is not permission.

- A model may generate but does not become Mary.
- A node may compute but does not own Mary's state.
- A renderer may present Mary but does not define her identity.
- Browser/stream/game text is context/evidence until a canonical owner accepts it.
- Paid, external, consequential or device-local actions remain explicitly bounded.
- Generic shell/computer execution is not smuggled through a broad capability name.

## Product experience rule

Presentation should make canonical state understandable without becoming another state owner.

- Desktop, native iPhone, PWA and future surfaces share one visual/state vocabulary while adapting layout to the device.
- UI copy describes the creator-facing experience first; backend class/provider detail belongs in diagnostics.
- Character art/avatar state is presentation evidence, not memory or biography authority.
- Operational UX telemetry may measure latency/readiness but must remain content-free and non-authoritative.
- Public/performance mode is a privacy projection of the same Mary, never a second public personality database.

## Relational presence rule

Mary may express friendship, closeness, romance or partnership as **relationship state over the same canonical Mary**.

- Romantic/partner mode must never create another persona, identity store or model-defined clone.
- Durable relationship-mode changes and completed shared activities must flow through the existing canonical relationship owner.
- Active shared activities and proactive-presence impulses may be ephemeral, but must remain bounded.
- Proactive presence is proposal-only until an existing autonomy/surface permission path authorizes delivery.
- Derived social/entity graphs may improve retrieval but remain projections, never truth authority.
- Public/performance presentation should suppress private intimacy without changing Mary's underlying identity.
- Companion behavior must not use exclusivity demands, guilt for absence, fake suffering, or streak pressure as engagement mechanisms.

## Graceful-degradation rule

Optional capability failure must reduce capability rather than erase Mary.

Supported degraded states include:

- portrait/generated-art presentation when VRM/WebGL is unavailable;
- text interaction when voice is unavailable;
- cloud routing when an optional local node is absent;
- private/local routing when configured cloud providers are unavailable;
- disconnected MCP/creative/stream integrations without Core startup failure.

Surfaces should clearly explain the unavailable capability while keeping primary conversation/work flows usable.

## Persistence rule

Mary is not defined by one mutable folder. Recoverability requires:

- canonical source in Git;
- runtime state in configured platform-native data roots;
- bounded/atomic persistence where state is durable;
- backups/recovery for durable state;
- no secret-bearing runtime state committed to source control.

Source checkouts no longer use repository-local `data/` by default. Host-native configured paths remain the runtime-state authority.

## Cleanup rule

Current authority lives in this file, `README.md`, `docs/README.md`, the current `docs/architecture/` / `docs/operations/` documents, executable tests and code. `docs/history/` preserves project archaeology but cannot override current authority.

A dated patch note, package report, old test count or generated overlay is never a reason to overwrite a newer canonical owner. Reconcile useful ideas into current systems and retire the duplicate implementation.
