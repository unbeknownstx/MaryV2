# Windows Headless Capability Node

The Windows node lets canonical remote Mary Core use approved local capabilities (currently including Ollama) without requiring Mary Desktop to be open.

## One-time permission

```powershell
python -m scripts.node_permissions allow llm.ollama
```

## Manual launch

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_windows_node.ps1
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
