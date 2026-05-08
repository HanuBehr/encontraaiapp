$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Warning "Backup your data before updating: .\scripts\client_backup.ps1"

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".git"))) {
    throw "This folder is not a Git checkout. Update from a new client package instead."
}

git pull
docker compose up -d --build

Write-Host "Update complete. Data in ./data was preserved." -ForegroundColor Green

