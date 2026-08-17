# MaryV2 Verification Guide

## Two different prompts

MaryV2 testing uses two interfaces. Do not mix them.

### PowerShell / VS Code terminal

A terminal prompt looks similar to:

```text
(.venv) PS C:\Users\Melvin\Documents\GitHub\MaryV2>
```

Run operating-system and Python commands here, for example:

```powershell
python main.py
python -m pytest tests -q
python -m scripts.run_diagnostics
python -m scripts.run_release_verification
Test-Path some_file.txt
Get-Content some_file.txt
Remove-Item some_file.txt
```

### Mary's interactive prompt

After `python main.py`, Mary displays:

```text
You:
```

Type requests for Mary here, for example:

```text
who are you?
remember that my test animal is a red panda
show me what's in mary/memory
analyze mary/memory/manager.py
create file test.txt with hello
approve
```

Do not type PowerShell commands at Mary's `You:` prompt. MaryV2 now detects common terminal-shaped commands and tells you to run them in PowerShell instead of sending them to the LLM.

## Approval shorthand

If exactly one tool request is pending, either form works:

```text
approve
```

or:

```text
approve request_<full-id>
```

Likewise, `reject` works when exactly one request is pending.

If multiple requests are pending, Mary refuses to guess. Use:

```text
/pending
```

and then approve or reject the exact request id.

## One-command verification

From PowerShell in the MaryV2 repository:

```powershell
python -m scripts.run_release_verification
```

This performs:

- Python compile checks
- the full pytest suite, including the configured live LLM test
- 30-system diagnostics
- local filesystem/code safety smoke tests

For a deterministic verification that skips the live LLM test:

```powershell
python -m scripts.run_release_verification --offline
```

To additionally authorize one explicit live public web research smoke test:

```powershell
python -m scripts.run_release_verification --live-web
```

The live web test is never performed unless `--live-web` is supplied.

## Interactive help

While Mary is running:

```text
/help
```

shows examples of what belongs at Mary's prompt versus PowerShell.

```text
/pending
```

shows pending tool approval requests.
