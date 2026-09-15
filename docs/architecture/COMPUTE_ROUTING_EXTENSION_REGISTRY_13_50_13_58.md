# MaryV2 13.50–13.58 — Compute Routing Extension Registry

This compact registry supplements `SYSTEM_REGISTRY.md` for the post-13.36 compute-routing extensions. It does not create a second authority map.

| Revision | Canonical implementation | Status | Authority / notes |
|---|---|---|---|
| 13.50 | `mary.distributed.tasks` | ACTIVE | Bounded claim leases, replay-safe rollover, stale-attempt isolation. Broker remains Core-owned. |
| 13.51 | `mary.distributed.compute_fabric.BenchmarkBook`, `HomeComputeScheduler` | ACTIVE ADVISORY | Content-free measured success/latency evidence; never permission or Mary memory. |
| 13.52 | `DeviceTaskBroker` claimed-work projection | ACTIVE ADVISORY | Core-derived realtime/background pressure; node cannot fabricate claimed-task counts. |
| 13.53 | `mary.distributed.resource_probe`, `resource_telemetry`, `mary.runtime.resource_reporting_gateway` | ACTIVE OPTIONAL | Fresh bounded RAM/accelerator pressure; asynchronous and fail-soft; telemetry stripped before task result retention. |
| 13.54 | `mary.distributed.resource_requirements`, existing 13.37 resource planner | ACTIVE ADVISORY | Explicit per-role accelerator-memory requirements only; no inference from model names; measured no-fit may exclude a candidate. |
| 13.55 | `BenchmarkBook.last_adaptive_decision` via broker compute status | ACTIVE DIAGNOSTIC | One bounded content-free explanation of the last adaptive route; no prompts/results/credentials. |
| 13.56 | `mary.distributed.resource_calibration`, `scripts.calibrate_model_fit` | ACTIVE OPERATOR TOOL | Cold-load model-fit measurement; recommendation requires proven Ollama cold→loaded transition. No automatic environment mutation. |
| 13.57 | role-aware `scripts.calibrate_model_fit` | ACTIVE OPERATOR TOOL | Measures `general`, `conversation`, `fast`, or `utility` using production device role mapping and emits only the matching fit recommendation. |
| 13.58 | `mary.distributed.resource_hint_provenance`, `resource_requirements` | ACTIVE GUARD | Optional role-specific provenance binds an applied fit hint to runtime/model/context. Mismatch suppresses only stale scheduling evidence; legacy hints remain compatible. |

Canonical details: `RESILIENT_COMPUTE_ROUTING_13_50_13_53.md` (currently covers behavior through 13.55) and `MODEL_FIT_CALIBRATION_13_56_13_58.md`.

All entries preserve the root rule: one Mary Core owns identity/state/authority; compute nodes are replaceable workers and scheduling evidence cannot grant capability or permission.
