# Script PowerShell pour arrêter Redis

Write-Host "Arrêt de Redis..." -ForegroundColor Yellow

docker stop prospectlab-redis

if ($LASTEXITCODE -eq 0) {
    Write-Host "Redis a été arrêté avec succès." -ForegroundColor Green
} else {
    Write-Host "Erreur lors de l'arrêt de Redis. Le conteneur n'existe peut-être pas." -ForegroundColor Red
}

