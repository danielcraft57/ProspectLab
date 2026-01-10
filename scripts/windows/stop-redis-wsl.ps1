# Script PowerShell pour arrêter Redis dans WSL

Write-Host "Arrêt de Redis dans WSL..." -ForegroundColor Yellow

$wslDistro = "Ubuntu"

wsl -d $wslDistro -e bash -c "sudo service redis-server stop" 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "Redis a été arrêté avec succès." -ForegroundColor Green
} else {
    Write-Host "Erreur lors de l'arrêt de Redis. Il n'est peut-être pas en cours d'exécution." -ForegroundColor Yellow
}


