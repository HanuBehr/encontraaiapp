$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$envPath = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing .env. Run .\scripts\client_install.ps1 first."
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return (($line -split "=", 2)[1]).Trim()
}

$requiredKeys = @("GOOGLE_API_KEY")
$missingKeys = @()
foreach ($key in $requiredKeys) {
    $value = Get-EnvValue -Path $envPath -Key $key
    if ([string]::IsNullOrWhiteSpace($value)) {
        $missingKeys += $key
    }
}

if ($missingKeys.Count -gt 0) {
    Write-Warning ("The following keys are blank in .env: " + ($missingKeys -join ", "))
}

$cnpjaKey = Get-EnvValue -Path $envPath -Key "CNPJA_API_KEY"
$cnpjSearchEnabled = Get-EnvValue -Path $envPath -Key "CNPJ_COMPANY_SEARCH_ENABLED"
if ($cnpjSearchEnabled -match "^(?i:true|1|yes)$" -and [string]::IsNullOrWhiteSpace($cnpjaKey)) {
    Write-Warning "CNPJ_COMPANY_SEARCH_ENABLED is true but CNPJA_API_KEY is blank. CNPJ enrichment will not be available."
}

docker compose up -d --build

Write-Host ""
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "Backend docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Backend health: http://localhost:8000/health" -ForegroundColor Green
