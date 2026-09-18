# Windows Home Capability Node

The canonical Windows home node lets remote Mary Core use approved local capabilities without requiring Mary Desktop to be open. Desktop remains a presentation surface by default and does not register a competing capability node.

## One-time permission

```powershell
python -m scripts.node_permissions allow llm.ollama
```

## Optional Mary self-repair worker

When this checkout has a local model available through Ollama/llama.cpp/LM Studio,
the same home node can act as Mary's bounded software-engineering worker.

Enable proposal/inspection first:

```powershell
python -m scripts.node_permissions allow engineering.repo.inspect
python -m scripts.node_permissions allow engineering.repair.plan
python -m scripts.node_permissions allow engineering.patch.propose
python -m scripts.node_permissions allow engineering.git.status
python -m scripts.node_permissions allow engineering.git.diff
python -m scripts.node_permissions allow engineering.structure.verify
python -m scripts.node_permissions allow engineering.tests.targeted
```

Repository writes stay separately disabled until you choose:

```powershell
python -m scripts.node_permissions allow engineering.repo.apply
```

After a repair passes verification, optional Git publication remains separately gated:

```powershell
python -m scripts.node_permissions allow engineering.git.commit
python -m scripts.node_permissions allow engineering.git.push
$env:MARY_ENGINEERING_PUSH_ENABLED = "true"  # only if you want explicit Push-that-fix support
```

Then Mary can use the creator-facing flow `Fix yourself` -> `Check the repair`
-> `Apply that fix` -> `Verify that fix`. Planning never writes, validation
runs in a disposable copied workspace, and the worker has no generic
shell/commit/push/deploy capability. This workspace isolation protects the live
checkout from normal test writes but is not an OS/VM containment boundary;
test execution therefore remains separately default-deny.

See `docs/architecture/ENGINEERING_WORKER_CURRENT.md`.

## Manual launch

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_home_node_windows.ps1
```

## Start automatically at user logon

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_node_task.ps1
```

Remove the scheduled task with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_windows_node_task.ps1
```

The task launches the node only. It does not launch Desktop and does not create a second Mary identity/state authority.


The older `launch_windows_node.ps1` and `scripts.run_windows_node` entrypoints are compatibility wrappers only; both delegate to `scripts.run_home_node`.
For the current RX 580 4 GB host, the canonical launcher applies the `windows-rx580-4gb` profile and bounded Ollama server settings before registration.
