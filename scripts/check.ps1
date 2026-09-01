# Run static checks across the monorepo (Windows PowerShell).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
Write-Host '==> Typecheck' -ForegroundColor Cyan
npm run typecheck
Write-Host '==> Lint' -ForegroundColor Cyan
npm run lint
Write-Host '==> Format check' -ForegroundColor Cyan
npm run format:check
Pop-Location
Write-Host '==> All checks passed' -ForegroundColor Green
