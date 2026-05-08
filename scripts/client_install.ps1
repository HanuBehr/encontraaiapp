$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "Checking Docker..." -ForegroundColor Cyan
docker --version | Out-Null
docker compose version | Out-Null

foreach ($folder in @("data", "exports", "backups")) {
    $target = Join-Path $projectRoot $folder
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path $target | Out-Null
    }
}

$envPath = Join-Path $projectRoot ".env"
$clientExamplePath = Join-Path $projectRoot "deploy\\client\\.env.client.example"

if (-not (Test-Path -LiteralPath $clientExamplePath)) {
    throw "Missing deploy\\client\\.env.client.example. Restore the client install template before continuing."
}

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $clientExamplePath -Destination $envPath
    Write-Warning "Edit .env and fill GOOGLE_API_KEY and CNPJA_API_KEY before starting."
}

Write-Host ""
Write-Host "Client install preparation complete." -ForegroundColor Green
Write-Host "Next command:" -ForegroundColor Yellow
Write-Host ".\scripts\client_start.ps1"
