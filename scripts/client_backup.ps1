$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$backupDir = Join-Path $projectRoot "backups"
$dataDir = Join-Path $projectRoot "data"
$exportsDir = Join-Path $projectRoot "exports"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (-not (Test-Path -LiteralPath $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$databasePath = Join-Path $dataDir "app.db"
if (Test-Path -LiteralPath $databasePath) {
    $dbBackupPath = Join-Path $backupDir "app-db-$timestamp.db"
    Copy-Item -LiteralPath $databasePath -Destination $dbBackupPath -Force
    Write-Host "Database backup created: $dbBackupPath" -ForegroundColor Green
} else {
    Write-Warning "Database file not found at data/app.db."
}

if (Test-Path -LiteralPath $exportsDir) {
    $exportFiles = Get-ChildItem -LiteralPath $exportsDir -Force -Recurse -File -ErrorAction SilentlyContinue
    if ($exportFiles) {
        $exportsArchivePath = Join-Path $backupDir "exports-$timestamp.zip"
        if (Test-Path -LiteralPath $exportsArchivePath) {
            Remove-Item -LiteralPath $exportsArchivePath -Force
        }
        Compress-Archive -Path (Join-Path $exportsDir "*") -DestinationPath $exportsArchivePath -Force
        Write-Host "Exports backup created: $exportsArchivePath" -ForegroundColor Green
    } else {
        Write-Host "No export files found to archive." -ForegroundColor Yellow
    }
}

