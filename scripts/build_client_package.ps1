$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stagingRoot = Join-Path $distRoot ("client-package-build-" + $timestamp)
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
        "*.tsbuildinfo",
        "*.pyc",
        "*.pyo"
    )

    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Robocopy failed while copying $Source."
    }
}

if (Test-Path -LiteralPath $zipPath) {
    try {
        Remove-Item -LiteralPath $zipPath -Force -ErrorAction Stop
    } catch {
        $zipPath = Join-Path $distRoot ("encontraai-client-package-" + $timestamp + ".zip")
        Write-Warning "Could not replace the existing zip. Using fallback path: $zipPath"
    }
}

New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

foreach ($folder in @("app", "web", "scripts", "docs", "deploy")) {
    Invoke-RobocopyCopy -Source (Join-Path $projectRoot $folder) -Destination (Join-Path $stagingRoot $folder)
}

foreach ($file in @(
    "README.md",
    "requirements.txt",
    "Dockerfile.backend",
    "docker-compose.yml",
    ".env.example",
    ".dockerignore",
    "pytest.ini"
)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination (Join-Path $stagingRoot $file) -Force
}

Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $zipPath -Force

try {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction Stop
} catch {
    Write-Warning "Temporary staging folder could not be removed automatically: $stagingRoot"
}

Write-Host "Client package created:" -ForegroundColor Green
Write-Host $zipPath
