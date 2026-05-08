$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist"
$packageRoot = Join-Path $distRoot "client-package"
$zipPath = Join-Path $distRoot "encontraai-client-package.zip"

function Invoke-RobocopyCopy {
    param(
        [string]$Source,
        [string]$Destination
    )

    $arguments = @(
        $Source,
        $Destination,
        "/E",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XD",
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".pycache_verify",
        "node_modules",
        ".next",
        "dist",
        "data",
        "exports",
        "backups",
        "/XF",
        ".env",
        "app.db",
        "*.pyc",
        "*.pyo"
    )

    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Robocopy failed while copying $Source."
    }
}

if (Test-Path -LiteralPath $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

foreach ($folder in @("app", "web", "scripts")) {
    Invoke-RobocopyCopy -Source (Join-Path $projectRoot $folder) -Destination (Join-Path $packageRoot $folder)
}

foreach ($file in @(
    "requirements.txt",
    "Dockerfile.backend",
    "docker-compose.yml",
    ".env.client.example",
    ".env.example",
    ".dockerignore",
    "README_CLIENT_INSTALL.md"
)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination (Join-Path $packageRoot $file) -Force
}

Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

Write-Host "Client package created:" -ForegroundColor Green
Write-Host $zipPath

