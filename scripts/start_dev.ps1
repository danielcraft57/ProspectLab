# Script de démarrage développement ProspectLab
# - app Flask dans cette fenêtre
# - Celery (worker + beat) dans une autre console via run_celery.py
#
# Files du worker : CELERY_WORKER_QUEUES dans .env (défaut config : toutes les files dont heavy).
# Équivalent typique : ... -Q celery,scraping,technical,seo,osint,pentest,heavy,website_full
# run_celery.py ajoute --pool=threads, --concurrency (config) et lance beat en parallèle.
#
# Usage : .\scripts\start_dev.ps1

$ErrorActionPreference = 'Stop'

# Répertoire du projet (parent du dossier scripts)
$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$EnvName = 'prospectlab'

# Chemin vers le python de l'env conda (par défaut Miniconda dans le profil utilisateur)
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
    Write-Host "❌ Impossible de trouver $PythonExe" -ForegroundColor Red
    Write-Host "   Vérifie le chemin de Miniconda / l'environnement '$EnvName'." -ForegroundColor Yellow
    exit 1
}

# Lancer Celery (worker + beat via run_celery.py) dans une nouvelle console
Write-Host "-> Lancement de Celery (worker + beat) dans une nouvelle fenêtre..." -ForegroundColor Yellow
$celeryProc = Start-Process -FilePath $PythonExe `
    -ArgumentList "run_celery.py" `
    -WorkingDirectory $PROJECT_DIR `
    -PassThru

Write-Host ""
Write-Host "-> Lancement de l'application Flask dans cette fenêtre..." -ForegroundColor Yellow
Write-Host "   (Ctrl+C ici N'ARRÊTE PAS Celery, ferme-le dans son autre fenêtre)" -ForegroundColor Gray
Write-Host ""

& $PythonExe "app.py"

