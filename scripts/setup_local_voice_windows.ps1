param(
    [switch]$InstallWhisper
)
$ErrorActionPreference = "Stop"
Write-Host "MaryV2 12.8 local voice setup" -ForegroundColor Magenta
Write-Host "Windows SAPI requires no extra install and is Mary's free local TTS fallback."
if ($InstallWhisper) {
    python -m pip install -r requirements-local-voice.txt
    Write-Host "Installed optional faster-whisper support." -ForegroundColor Green
} else {
    Write-Host "Skipping faster-whisper. Re-run with -InstallWhisper when ready." -ForegroundColor DarkGray
}
Write-Host "For higher-quality local TTS later, configure Piper in .env:" -ForegroundColor Cyan
Write-Host "  MARY_PIPER_EXECUTABLE=C:\MaryTools\piper\piper.exe"
Write-Host "  MARY_PIPER_MODEL=C:\MaryTools\piper\mary.onnx"
Write-Host "  MARY_TTS_PROVIDER=local_first"
