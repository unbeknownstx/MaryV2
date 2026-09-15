# MaryV2 13.4 — OpenHands software-engineering worker boundary

OpenHands is not Mary Core, not Mary's identity, and not a general-purpose
device executor.

This document defines the intended integration boundary only. No OpenHands
runtime is added to Mary Core by the 13.4 MCP work.

## Role

OpenHands may later serve as a **separate sandboxed software-engineering
worker** for repository tasks such as:

- inspect a checked-out codebase;
- implement a bounded engineering request;
- run project-local tests and linters;
- return a patch/diff, test logs, changed-file manifest, and diagnostics.

Mary may formulate or review a worker job, but the worker remains replaceable
infrastructure. Its output is evidence/proposed code until accepted through the
normal creator/repository workflow.

## Non-authority rules

An OpenHands worker must never own or directly mutate:

- Mary identity or Character Core;
- relationship state;
- lived memory;
- developed-self/personality state;
- agency/goals;
- emotion state;
- canonical continuity state;
- node enrollment trust;
- Mary Core session credentials.

The worker must not mount Mary's durable state directory.

## Sandbox

The future worker should run in a separate container, VM, or equivalent
sandbox with a task-specific workspace.

The sandbox may have a shell **inside its own isolated engineering
environment**, because software engineering requires build/test commands. That
does not create a Mary device-shell capability. Mary Core still has no
arbitrary shell task type.

Recommended boundaries:

1. disposable repo clone or dedicated worktree;
2. no host filesystem outside explicit workspace mounts;
3. no host `.env` or Mary credential store;
4. no `MARY_CORE_TOKEN` or capability-node durable credential;
5. network denied by default, then narrowly enabled per job when required;
6. CPU/memory/time quotas;
7. explicit repository scope;
8. immutable job specification and audit identifier;
9. output-size limits and secret scanning;
10. sandbox destroyed or reset after the job.

## Credentials

If repository write access is ever required, issue a short-lived,
repository-scoped worker credential with the minimum permissions necessary.

Do not give the worker:

- the creator's broad personal GitHub credential;
- Mary Core bearer credentials;
- capability-node enrollment/session tokens;
- unrelated API keys.

Prefer read-only jobs by default. A worker that can create a branch or PR still
must not merge automatically.

## Proposed job contract

A future worker adapter should accept a typed job resembling:

```json
{
  "repository": "owner/repo",
  "base_ref": "main",
  "task": "Implement bounded feature X",
  "allowed_paths": ["mary/", "tests/", "docs/"],
  "network_policy": "deny",
  "write_policy": "workspace_only",
  "requested_checks": [
    "python -m scripts.verify_repository_structure",
    "python -m pytest -q"
  ]
}
```

The command list belongs to the **sandbox worker contract**, not
`DeviceTaskBroker`. Core must not translate this into a host shell request.

## Output contract

The worker should return only bounded engineering artifacts:

- base commit SHA;
- resulting workspace commit SHA if one was created;
- changed-file list;
- unified diff or patch reference;
- structure/test/lint results;
- warnings and unresolved failures;
- provenance and worker version.

Raw environment variables, auth headers, secret files, and unrelated workspace
contents must be stripped.

## Approval flow

Recommended sequence:

```text
Mary/creator formulates bounded engineering intent
    -> creator authorizes worker job
    -> isolated OpenHands sandbox executes
    -> patch + test evidence returned
    -> Mary/creator reviews
    -> explicit creator authorization for repository write/PR
    -> PR opened
    -> merge remains separate and explicit
```

Autonomy remains proposal-only. Worker availability or successful tests are
not permission to push, open a PR, merge, deploy, spend money, or change Mary's
canonical state.

## Relationship to the MCP fabric

OpenHands is deliberately not listed in `MCP_CAPABILITIES`.

OpenDesign, Scrapling, and Langflow are narrow tool servers consumed by a
permission-bounded capability node. OpenHands is a higher-risk engineering
worker with its own sandbox, job lifecycle, credential model, and approval
boundary.

If OpenHands itself exposes MCP in the future, Mary should still talk to a
dedicated worker gateway that enforces this contract rather than treating it
as another ordinary MCP tool server.
