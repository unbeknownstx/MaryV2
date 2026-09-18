# MaryV2 — Bounded Local Engineering Worker

Mary can delegate software-engineering work to a connected Mac/Windows/Linux
home node without moving identity, memory, relationship state, permissions or
canonical authority out of Mary Core.

## Authority

The worker is **not Mary**. It is replaceable infrastructure beneath Core.

- Mary Core interprets the creator's request and owns the conversational flow.
- The capability node owns local execution permission.
- A local model (Ollama, llama.cpp, LM Studio through `llm.local`, etc.) is a
  replaceable reasoning worker.
- Repository evidence, diffs and test results are engineering evidence only.
- Repository changes never become identity/memory evidence automatically.

There is no generic remote shell capability.

## Typed capabilities

The current node worker advertises:

- `engineering.repo.inspect` — bounded source inspection.
- `engineering.repair.plan` — use the node's configured local model to produce
  an evidence-grounded exact-edit proposal.
- `engineering.patch.propose` — calculate an exact diff without writing.
- `engineering.repo.apply` — write exactly one previously proposed patch;
  this is a separate local permission and requires an explicit creator apply
  request.
- `engineering.structure.verify` — run repository-structure verification in a
  disposable isolated workspace.
- `engineering.tests.targeted` — run explicitly named `tests/*.py` files in a
  disposable isolated workspace.
- `engineering.tests.full` — run the deterministic pytest suite in a
  disposable isolated workspace.
- `engineering.git.status` / `engineering.git.diff` — read-only repository
  state.

`git commit`, `git push`, PR merge, production deploy, dependency install,
root/admin execution and arbitrary shell commands are intentionally absent.

## Local-model requirement

`engineering.repair.plan` is advertised as ready only when the node can reach
its configured `LocalRuntimeProvider(role="general")`. That runtime may resolve
to Ollama, llama.cpp, LM Studio or another supported local runtime according to
the existing local-runtime policy.

Loading a model does not grant repository access. The engineering capability
must also be allowed locally.

## Permission model

All engineering capabilities are default-deny in
`~/.maryv2/device_permissions.json`.

A useful read/plan/verify setup is:

```bash
python -m scripts.node_permissions allow engineering.repo.inspect
python -m scripts.node_permissions allow engineering.repair.plan
python -m scripts.node_permissions allow engineering.patch.propose
python -m scripts.node_permissions allow engineering.git.status
python -m scripts.node_permissions allow engineering.git.diff
python -m scripts.node_permissions allow engineering.structure.verify
python -m scripts.node_permissions allow engineering.tests.targeted
```

Keep repository mutation disabled until desired:

```bash
python -m scripts.node_permissions allow engineering.repo.apply
```

Full-suite execution is separately opt-in:

```bash
python -m scripts.node_permissions allow engineering.tests.full
```

Deny any capability again with `scripts.node_permissions deny <capability>`.

## Repository discovery

The worker uses `MARY_ENGINEERING_REPO_ROOT` when set. Otherwise it searches
the current working directory and its parents for a MaryV2 Git checkout.

The home node should normally be launched from the MaryV2 checkout. The worker
never receives Mary Core bearer credentials as model context.

## Repair flow

A normal creator-facing flow is:

```text
Creator: Fix yourself / fix your own code
  -> Mary Core routes engineering_repair
  -> Core selects an authorized engineering.repair.plan node
  -> node inspects bounded repository evidence
  -> local model proposes exact old->new edits
  -> node validates syntax/diff and stores exact proposal locally
  -> Core receives only bounded manifest + diff + proposal id

Creator: Check the repair
  -> Mary shows the proposal/diff

Creator: Apply that fix
  -> Core requires engineering.repo.apply to be locally authorized
  -> node applies only the exact stored proposal
  -> SHA-256 preconditions reject stale source
  -> no commit/push/merge/deploy occurs

Creator: Verify that fix
  -> typed repository verification runs in a disposable copied workspace
```

Proposal IDs are node-local and short-lived. Restarting the node invalidates
them. Core treats them as one-shot for apply.

## Workspace isolation and stronger sandboxing

Planning never writes source. Test/structure commands execute only in a
disposable copy of the working tree. The copy excludes Git metadata,
virtualenvs, Mary durable data, common credential files, symlinks, caches and
generated outputs.

The test executor uses fixed argv arrays with `shell=False`. Core cannot send
a command string. This protects the live checkout from normal test writes, but
it is **not an OS/VM containment boundary**: Python tests can still exercise the
host permissions of the node process. Test capabilities therefore remain
separately default-deny. For hostile/untrusted code or stronger filesystem and
network isolation, use the future OpenHands/container worker boundary instead.

Repository apply is the one exception to sandbox-only writes: it modifies the
selected MaryV2 checkout, but only after the separate node permission and an
explicit creator apply phrase. Every file requires the exact SHA-256 captured
when the proposal was created.

## OpenHands relationship

This worker implements Mary's native bounded engineering loop. OpenHands may
still be connected later as a stronger **separate sandboxed engineering
backend**. It must obey the same authority and approval contract and must never
become Mary Core or a general device-shell capability.
