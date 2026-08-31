param(
    [switch]$Apply,
    [switch]$RemoveSource,
    [string]$DataDir
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Arguments = @("-m", "scripts.migrate_repo_state")
if ($Apply) { $Arguments += "--apply" }
if ($RemoveSource) { $Arguments += "--remove-source" }
if ($DataDir) {
    $Arguments += "--data-dir"
    $Arguments += $DataDir
}

# DRY RUN ONLY is the delegated Python command's default.
& python @Arguments
exit $LASTEXITCODE
