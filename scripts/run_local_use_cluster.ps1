# Lance l'application Flask en local en utilisant le cluster (Redis + workers sur node15/node13/node14).
# Charge les variables depuis .env.cluster sans modifier .env.
# Usage: .\scripts\run_local_use_cluster.ps1

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env.cluster'

if (-not (Test-Path $envFile)) {
    $example = Join-Path $projectRoot 'env.cluster.example'
    if (Test-Path $example) {
        Write-Host "Fichier .env.cluster absent. Copie de env.cluster.example vers .env.cluster..." -ForegroundColor Yellow
        Copy-Item $example $envFile
        Write-Host "Edite .env.cluster (host Redis, DATABASE_URL si besoin) puis relance ce script." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Fichier .env.cluster absent et env.cluster.example introuvable." -ForegroundColor Red
    exit 1
}

# Charger .env.cluster dans l'environnement du processus (sans écraser .env)
foreach ($line in Get-Content $envFile -Encoding UTF8) {
    $line = $line.Trim()
    if ($line -eq '' -or $line.StartsWith('#')) { continue }
    if ($line -match '^([^#=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Substring(1, $val.Length - 2) }
        if ($val.StartsWith("'") -and $val.EndsWith("'")) { $val = $val.Substring(1, $val.Length - 2) }
        [Environment]::SetEnvironmentVariable($key, $val, 'Process')
    }
}

# Charger aussi .env pour le reste (SECRET_KEY, MAIL_*, etc.) si présent ; .env.cluster a déjà été chargé, les valeurs de .env.cluster priment car chargées en premier
$envDefault = Join-Path $projectRoot '.env'
if (Test-Path $envDefault) {
    foreach ($line in Get-Content $envDefault -Encoding UTF8) {
        $line = $line.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { continue }
        if ($line -match '^([^#=]+)=(.*)$') {
            $key = $matches[1].Trim()
            if ([Environment]::GetEnvironmentVariable($key, 'Process') -eq $null -or [Environment]::GetEnvironmentVariable($key, 'Process') -eq '') {
                $val = $matches[2].Trim()
                if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Substring(1, $val.Length - 2) }
                if ($val.StartsWith("'") -and $val.EndsWith("'")) { $val = $val.Substring(1, $val.Length - 2) }
                [Environment]::SetEnvironmentVariable($key, $val, 'Process')
            }
        }
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ProspectLab - mode local + cluster" -ForegroundColor Cyan
Write-Host "Broker/Backend: $($env:CELERY_BROKER_URL)" -ForegroundColor Gray
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $projectRoot
python app.py
