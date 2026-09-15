$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "MaryV2 .venv was not found. Run scripts\setup_windows.ps1 first."
}

# Keep the generated Vite bundle synchronized with checked-in Desktop source.
# Both the Qt Desktop and Launcher serve desktop\dist; without this guard a
# source pull can appear to have done nothing because an older bundle remains.
$DesktopRoot = Join-Path $Root "desktop"
$DistIndex = Join-Path $DesktopRoot "dist\index.html"
$NeedsBuild = -not (Test-Path $DistIndex)

if (-not $NeedsBuild) {
    $DistTime = (Get-Item $DistIndex).LastWriteTimeUtc
    $FreshnessRoots = @(
        (Join-Path $DesktopRoot "src"),
        (Join-Path $DesktopRoot "public")
    )
    $FreshnessFiles = @(
        (Join-Path $DesktopRoot "index.html"),
        (Join-Path $DesktopRoot "launcher.html"),
        (Join-Path $DesktopRoot "vite.config.js"),
        (Join-Path $DesktopRoot "package.json"),
        (Join-Path $DesktopRoot "package-lock.json")
    )

    foreach ($Path in $FreshnessRoots) {
        if (Test-Path $Path) {
            $Newer = Get-ChildItem -Path $Path -Recurse -File |
                Where-Object { $_.LastWriteTimeUtc -gt $DistTime } |
                Select-Object -First 1
            if ($Newer) {
                $NeedsBuild = $true
                break
            }
        }
    }

    if (-not $NeedsBuild) {
        foreach ($Path in $FreshnessFiles) {
            if ((Test-Path $Path) -and ((Get-Item $Path).LastWriteTimeUtc -gt $DistTime)) {
                $NeedsBuild = $true
                break
            }
        }
    }
}

if ($NeedsBuild) {
    $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $Npm) {
        $Npm = Get-Command npm -ErrorAction SilentlyContinue
    }
    if (-not $Npm) {
        throw "Desktop source changed but npm is not available. Install Node/npm or run scripts\setup_windows.ps1."
    }

    Push-Location $DesktopRoot
    try {
        if (-not (Test-Path "node_modules\.bin\vite.cmd")) {
            Write-Host "MaryV2: installing Desktop frontend dependencies..."
            & $Npm.Source ci
            if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE." }
        }

        Write-Host "MaryV2: rebuilding Desktop frontend..."
        & $Npm.Source run check
        if ($LASTEXITCODE -ne 0) { throw "npm run check failed with exit code $LASTEXITCODE." }
        & $Npm.Source run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed with exit code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
    }
}

# The launcher and source desktop share the same future frozen-app state.
if (-not $env:MARY_DATA_DIR) {
    if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is not available." }
    $env:MARY_DATA_DIR = Join-Path $env:LOCALAPPDATA "MaryV2\data"
}
if (-not $env:MARY_ENV_FILE -and (Test-Path ".env")) {
    $env:MARY_ENV_FILE = Join-Path $Root ".env"
}

& $Python -m scripts.run_launcher
exit $LASTEXITCODE
