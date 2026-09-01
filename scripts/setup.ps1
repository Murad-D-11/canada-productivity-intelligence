# Cross-workspace setup for Windows PowerShell.
# Installs Node workspace dependencies and creates the Python ML environment.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Write-Host '==> Installing Node workspace dependencies' -ForegroundColor Cyan
Push-Location $root
npm install
Pop-Location

Write-Host '==> Setting up Python ML environment' -ForegroundColor Cyan
Push-Location (Join-Path $root 'ml')
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Pop-Location

Write-Host '==> Setup complete' -ForegroundColor Green
