param(
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [string]$RepoPath = "C:\Users\Melvin\Documents\GitHub\MaryV2"
)
$ErrorActionPreference = "Stop"
& python "$PSScriptRoot\rollback_convergence.py" --backup $BackupPath --repo $RepoPath
exit $LASTEXITCODE
