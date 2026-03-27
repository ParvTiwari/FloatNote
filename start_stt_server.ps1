$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root "floatnote_env\Scripts\python.exe"
$server = Join-Path $root "stt_server.py"
$stdoutLog = Join-Path $root "stt_server.out.log"
$stderrLog = Join-Path $root "stt_server.err.log"

if (-not (Test-Path $python)) {
    throw "Python executable not found at $python"
}

Push-Location $root
try {
    Write-Host "Using Python:" $python
    Write-Host "Working directory:" $root
    Write-Host "Starting STT server..."
    & $python $server 1>> $stdoutLog 2>> $stderrLog
}
finally {
    Pop-Location
}
