param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendRoot = Join-Path $ProjectRoot "frontend"

Set-Location $ProjectRoot

$RuntimeRoot = Join-Path $ProjectRoot "backend\.runtime"
$LocalSecretPath = Join-Path $RuntimeRoot "local-deploy-jwt-secret.txt"
if (-not $env:JWT_SECRET_KEY) {
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    if (Test-Path $LocalSecretPath) {
        $env:JWT_SECRET_KEY = (Get-Content -LiteralPath $LocalSecretPath -Raw).Trim()
    } else {
        $env:JWT_SECRET_KEY = [Convert]::ToBase64String([Guid]::NewGuid().ToByteArray()) + [Convert]::ToBase64String([Guid]::NewGuid().ToByteArray())
        Set-Content -LiteralPath $LocalSecretPath -Value $env:JWT_SECRET_KEY -Encoding UTF8
    }
    Write-Warning "JWT_SECRET_KEY is not set. Using backend\.runtime\local-deploy-jwt-secret.txt for local deployment."
}

if (-not $env:DEFAULT_SUPER_ADMIN_PASSWORD) {
    Write-Warning "DEFAULT_SUPER_ADMIN_PASSWORD is not set. First bootstrap will keep admin / 123456."
}

$env:APP_HOST = $HostAddress
$env:APP_PORT = [string]$Port
$env:FRONTEND_DIST_DIR = Join-Path $FrontendRoot "dist"

Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location $FrontendRoot
npm run build
Pop-Location

$addresses = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.PrefixOrigin -ne "WellKnown"
    } |
    Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "Excel Check local deployment is starting..." -ForegroundColor Green
Write-Host "Local health: http://127.0.0.1:$Port/health"
foreach ($address in $addresses) {
    Write-Host "LAN URL:      http://$address`:$Port"
}
Write-Host ""
Write-Host "If other computers cannot open the URL, allow TCP port $Port in Windows Firewall."
Write-Host ""

python backend/run.py
