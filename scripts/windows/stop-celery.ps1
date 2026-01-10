# Script pour arrêter Celery proprement

Write-Host "Arrêt de Celery..." -ForegroundColor Yellow

# Trouver les processus Celery
$celeryProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*celery*worker*" -or $_.MainWindowTitle -like "*celery*"
}

if ($celeryProcesses) {
    Write-Host "Processus Celery trouvés: $($celeryProcesses.Count)" -ForegroundColor Cyan
    
    foreach ($proc in $celeryProcesses) {
        Write-Host "Arrêt du processus $($proc.Id)..." -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "Celery arrêté." -ForegroundColor Green
} else {
    Write-Host "Aucun processus Celery trouvé." -ForegroundColor Yellow
}

