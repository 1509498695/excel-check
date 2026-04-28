param()

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendRoot = Join-Path $ProjectRoot "frontend"

Set-Location $ProjectRoot

Write-Host "Checking backend style..." -ForegroundColor Cyan
python -m ruff check backend

Write-Host "Running backend tests..." -ForegroundColor Cyan
python -m pytest backend/tests -q

Write-Host "Checking frontend style..." -ForegroundColor Cyan
Push-Location $FrontendRoot
npm run lint

Write-Host "Building frontend..." -ForegroundColor Cyan
npm run build
Pop-Location

Write-Host "All standard checks passed." -ForegroundColor Green
