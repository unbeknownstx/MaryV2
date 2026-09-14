# Disposable Specialist Workers 13.41

MaryV2 13.41 adds a bounded worker envelope for task-local specialists. The design is inspired by the useful parts of local-agent systems such as Locally Uncensored, but it preserves Mary's existing authority model: one Mary Core owns identity/state, while workers are replaceable task executors.

## Core rule

A specialist worker is not another Mary. It owns no canonical identity, no durable memory, no creator profile, and no autonomous permission source.

Workers receive an explicit **narrowed delegation** from a parent task/runtime. They may use only capabilities present in the parent envelope, and mutation authority must be delegated separately from read/analysis capability.

## `mary.orchestration.workers`

The module provides:

- `WorkerBudget`: hard limits for steps, tool calls, provider calls, wall-clock lifetime, and returned text size;
- `SpecialistWorkerSpec`: immutable task/role/delegation description;
- `SpecialistWorkerSession`: process-local lifecycle, budget accounting, cancellation and delegated-capability checks;
- `SpecialistWorkerPool`: bounded registry for multiple disposable workers.

## Permission inheritance

Worker permission follows a strict subset rule:

`worker capabilities ⊆ parent capabilities`

Mutation is even narrower:

`worker mutating capabilities ⊆ parent mutating capabilities ⊆ parent capabilities`

A worker cannot add `shell.execute`, filesystem writes, MCP tools, provider access, or any other capability that the parent did not explicitly possess and delegate.

This envelope is still not final execution permission. Actual actions continue to terminate at Mary's existing `ToolManager`, `DeviceTaskBroker`, MCP allowlists, provider routing policy, and creator-approval boundaries.

## Cancellation and budgets

Workers can be cancelled by their parent/task. Terminal workers cannot continue making calls. Hard ceilings prevent a broken specialist loop from consuming an unbounded amount of compute or provider quota.

Budget exhaustion produces a terminal worker state rather than silently resetting counters or spawning another worker.

## No hidden background authority

13.41 intentionally does not create a new thread/process executor. It defines the worker contract that an existing authorized orchestration path can use. This avoids adding a second execution system beside `TaskOrchestrator + OrchestrationExecutor`.

A later runtime may schedule these workers concurrently, but concurrency must preserve the same inherited permissions, cancellation, resource serialization, and 13.37 progress/loop safeguards.

## Relationship to existing Mary task workspaces

`TaskWorkspaceManager` remains the canonical owner of ephemeral task evidence, hypotheses, actions, consultations and decisions. Worker output can be submitted into that workspace through existing orchestration paths, but a worker cannot promote its own output into Mary's durable semantic/episodic memory.

This keeps the architecture clean:

- task workspace = temporary work/evidence;
- specialist worker = temporary bounded executor envelope;
- Mary Core = identity, durable state and interpretation authority.
