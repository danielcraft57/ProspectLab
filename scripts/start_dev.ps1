# Script de démarrage développement ProspectLab
# - app Flask dans cette fenêtre
# - Celery (worker + beat) dans une autre console via run_celery.py
#
# Prérequis : Redis joignable (CELERY_BROKER_URL dans .env). Hors VPN LAN :
#   commenter node13 dans .env, utiliser redis://127.0.0.1:6379/0
#   puis .\scripts\windows\start-redis.ps1 (Docker)
#
# Usage : .\scripts\start_dev.ps1

$ErrorActionPreference = 'Stop'

$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$EnvName = 'prospectlab'
$PythonExe = Join-Path $env:USERPROFILE "miniconda3\envs\$EnvName\python.exe"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Démarrage ProspectLab (dev)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Projet : $PROJECT_DIR" -ForegroundColor Gray
Write-Host "Environnement conda : $EnvName" -ForegroundColor Gray
Write-Host "Python : $PythonExe" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $PythonExe)) {
    Write-Host "Impossible de trouver $PythonExe" -ForegroundColor Red
    Write-Host "Verifie Miniconda / l'environnement '$EnvName'." -ForegroundColor Yellow
    exit 1
}

Write-Host "-> Verification Redis + config Facebook..." -ForegroundColor Yellow
$pyCheck = @"
import sys
sys.path.insert(0, r'$PROJECT_DIR')
from config import CELERY_BROKER_URL, FACEBOOK_PROSPECTION_ENABLED
try:
    import redis
    client = redis.Redis.from_url(CELERY_BROKER_URL, socket_connect_timeout=4)
    client.ping()
    print('REDIS_OK')
except Exception as exc:
    print('REDIS_FAIL')
    print(CELERY_BROKER_URL)
    print(exc)
print('FB_ENABLED=' + ('1' if FACEBOOK_PROSPECTION_ENABLED else '0'))
"@
$checkLines = & $PythonExe -c $pyCheck 2>&1
$checkText = ($checkLines | Out-String).Trim()
if ($checkText -match 'REDIS_FAIL') {
    Write-Host ""
    Write-Host "Redis injoignable (Celery + Socket.IO en panne)." -ForegroundColor Red
    Write-Host "URL configuree dans .env :" -ForegroundColor Yellow
    ($checkLines | Select-Object -Skip 1 | Select-Object -First 1) | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    Write-Host ""
    Write-Host "  Verifie Redis sur node13 : systemctl status redis-server" -ForegroundColor White
    Write-Host '  Test manuel (racine projet) : python -c "import redis; from config import CELERY_BROKER_URL; print(redis.from_url(CELERY_BROKER_URL).ping())"' -ForegroundColor Gray
    Write-Host ""
    Write-Host "Arret : corrige Redis avant de relancer start_dev.ps1" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Redis OK." -ForegroundColor Green
}
if ($checkText -match 'FB_ENABLED=0') {
    Write-Host "FACEBOOK_PROSPECTION_ENABLED=false dans .env -> onglet Facebook desactive." -ForegroundColor Yellow
    Write-Host "Ajoute FACEBOOK_PROSPECTION_ENABLED=true puis redemarre Flask + Celery." -ForegroundColor Yellow
} else {
    Write-Host "Prospection Facebook activee." -ForegroundColor Green
}
Write-Host ""

Write-Host "-> Lancement de Celery (worker + beat) dans une nouvelle fenêtre..." -ForegroundColor Yellow
$null = Start-Process -FilePath $PythonExe `
    -ArgumentList "run_celery.py" `
    -WorkingDirectory $PROJECT_DIR `
    -PassThru

Write-Host ""
Write-Host "-> Lancement de l'application Flask dans cette fenêtre..." -ForegroundColor Yellow
Write-Host "   (Ctrl+C ici N'ARRETE PAS Celery, ferme-le dans son autre fenêtre)" -ForegroundColor Gray
Write-Host ""

Set-Location $PROJECT_DIR
& $PythonExe "app.py"
