# FloatNote - dev runner
# Launches the backend (Python), the React app (Vite), and Electron,
# each in its own PowerShell window.
#
# Usage:
#   .\run.ps1               # start all three
#   .\run.ps1 -NoElectron   # backend + react only
#
# Requires: root .venv (Python deps installed), npm deps installed in
# frontend\react-app and frontend\electron.

param(
    [switch]$NoElectron
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Warning "Root .venv not found at $venvPython - falling back to 'python' on PATH."
    $venvPython = "python"
}

$backendDir  = Join-Path $root "backend"
$reactDir    = Join-Path $root "frontend\react-app"
$electronDir = Join-Path $root "frontend\electron"

Write-Host "Starting FloatNote dev stack..." -ForegroundColor Cyan

# 1) Backend - python main.py (run from backend\ so ai_modules resolves)
Write-Host "  -> Backend  : $backendDir" -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backendDir'; & '$venvPython' main.py"
)

# 2) React app - npm run dev
Write-Host "  -> React app: $reactDir" -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$reactDir'; npm run dev"
)

# 3) Electron - npm start (give Vite a moment to come up first)
if (-not $NoElectron) {
    Write-Host "  -> Electron : $electronDir" -ForegroundColor Green
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$electronDir'; Start-Sleep -Seconds 3; npm start"
    )
}

Write-Host "All processes launched in separate windows. Close those windows to stop." -ForegroundColor Cyan
