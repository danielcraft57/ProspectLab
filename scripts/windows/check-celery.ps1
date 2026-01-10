# Script pour vérifier l'état de Celery

Write-Host "Vérification de l'état de Celery..." -ForegroundColor Green
Write-Host ""

# Vérifier si Celery est en cours d'exécution
$celeryProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*celery*worker*" -or $_.MainWindowTitle -like "*celery*"
}

if ($celeryProcesses) {
    Write-Host "✓ Celery semble être en cours d'exécution" -ForegroundColor Green
    Write-Host "  Processus trouvés: $($celeryProcesses.Count)" -ForegroundColor Cyan
} else {
    Write-Host "✗ Celery n'est pas en cours d'exécution" -ForegroundColor Red
    Write-Host ""
    Write-Host "Pour démarrer Celery:" -ForegroundColor Yellow
    Write-Host "  1. Active l'environnement conda: conda activate prospectlab" -ForegroundColor Cyan
    Write-Host "  2. Lance Celery: celery -A celery_app worker --loglevel=info --pool=solo" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Ou utilise le script:" -ForegroundColor Yellow
    Write-Host "  .\scripts\windows\start-celery.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Note: Sur Windows, utilise --pool=solo (prefork n'est pas supporté)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Vérification de la configuration Redis..." -ForegroundColor Yellow

# Vérifier la configuration depuis .env ou config.py
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "CELERY_BROKER_URL=(.+)") {
        $brokerUrl = $matches[1].Trim()
        Write-Host "  BROKER_URL: $brokerUrl" -ForegroundColor Cyan
    }
    if ($envContent -match "CELERY_RESULT_BACKEND=(.+)") {
        $resultBackend = $matches[1].Trim()
        Write-Host "  RESULT_BACKEND: $resultBackend" -ForegroundColor Cyan
    }
}

# Extraire l'host et le port depuis l'URL
if ($brokerUrl -match "redis://([^:]+):(\d+)/(\d+)") {
    $redisHost = $matches[1]
    $redisPort = $matches[2]
    $redisDb = $matches[3]
    
    Write-Host ""
    Write-Host "Test de connexion Redis sur ${redisHost}:${redisPort} (DB ${redisDb})..." -ForegroundColor Yellow
    
    $connection = Test-NetConnection -ComputerName $redisHost -Port $redisPort -WarningAction SilentlyContinue
    
    if ($connection.TcpTestSucceeded) {
        Write-Host "✓ Redis est accessible" -ForegroundColor Green
    } else {
        Write-Host "✗ Redis n'est pas accessible" -ForegroundColor Red
        Write-Host "  Vérifiez que Redis est démarré sur ${redisHost}:${redisPort}" -ForegroundColor Yellow
    }
}

