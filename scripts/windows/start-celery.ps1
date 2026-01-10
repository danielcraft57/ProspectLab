# Script pour démarrer Celery

Write-Host "Démarrage de Celery..." -ForegroundColor Green
Write-Host ""

# Vérifier que nous sommes dans le bon répertoire
if (-not (Test-Path "celery_app.py")) {
    Write-Host "ERREUR: Ce script doit être exécuté depuis le répertoire du projet" -ForegroundColor Red
    Write-Host "Répertoire actuel: $PWD" -ForegroundColor Yellow
    exit 1
}

# Vérifier la configuration Redis
Write-Host "Vérification de la configuration Redis..." -ForegroundColor Yellow
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "CELERY_BROKER_URL=(.+)") {
        $brokerUrl = $matches[1].Trim()
        Write-Host "  BROKER_URL: $brokerUrl" -ForegroundColor Cyan
        
        # Extraire l'host et le port
        if ($brokerUrl -match "redis://([^:]+):(\d+)/(\d+)") {
            $redisHost = $matches[1]
            $redisPort = $matches[2]
            
            Write-Host "  Test de connexion Redis sur ${redisHost}:${redisPort}..." -ForegroundColor Yellow
            $connection = Test-NetConnection -ComputerName $redisHost -Port $redisPort -WarningAction SilentlyContinue
            
            if (-not $connection.TcpTestSucceeded) {
                Write-Host "  ✗ Redis n'est pas accessible!" -ForegroundColor Red
                Write-Host "  Vérifiez que Redis est démarré sur ${redisHost}:${redisPort}" -ForegroundColor Yellow
                exit 1
            } else {
                Write-Host "  ✓ Redis est accessible" -ForegroundColor Green
            }
        }
    }
}

Write-Host ""
Write-Host "Démarrage de Celery worker..." -ForegroundColor Yellow
Write-Host "Appuyez sur Ctrl+C pour arrêter Celery" -ForegroundColor Cyan
Write-Host ""

# Option pour effacer les logs au démarrage
# Décommentez les lignes suivantes si vous voulez effacer les logs à chaque démarrage
# if (Test-Path "logs\celery.log") { Remove-Item "logs\celery.log" -Force; Write-Host "Log Celery effacé" -ForegroundColor Yellow }
# if (Test-Path "logs\*.log") { Remove-Item "logs\*.log" -Force; Write-Host "Tous les logs effacés" -ForegroundColor Yellow }

Write-Host "Logs disponibles dans le dossier: logs\" -ForegroundColor Cyan
Write-Host "  - celery.log : Logs du worker Celery" -ForegroundColor Gray
Write-Host "  - prospectlab.log : Logs de l'application Flask" -ForegroundColor Gray
Write-Host "  - *.log : Logs des différentes tâches" -ForegroundColor Gray
Write-Host ""

# Activer l'environnement conda et lancer Celery
$condaEnv = "prospectlab"

# Vérifier si conda est disponible
$condaPath = Get-Command conda -ErrorAction SilentlyContinue
if (-not $condaPath) {
    Write-Host "ERREUR: Conda n'est pas trouvé dans le PATH" -ForegroundColor Red
    Write-Host "Activez manuellement l'environnement conda puis lancez:" -ForegroundColor Yellow
    Write-Host "  celery -A celery_app worker --loglevel=info" -ForegroundColor Cyan
    exit 1
}

# Lancer Celery avec le mode solo pour Windows
Write-Host "Lancement de Celery (mode solo pour Windows)..." -ForegroundColor Green
Write-Host "Note: Pour arrêter Celery, utilisez Ctrl+C ou le script stop-celery.ps1" -ForegroundColor Cyan
Write-Host ""

# Utiliser le wrapper Python pour une meilleure gestion de Ctrl+C
if (Test-Path "run_celery.py") {
    Write-Host "Utilisation du wrapper Python pour une meilleure gestion de Ctrl+C..." -ForegroundColor Cyan
    Write-Host ""
    
    # Obtenir le chemin Python de l'environnement conda directement
    # Cela évite d'utiliser 'conda run' qui peut bloquer les signaux
    $condaBase = & conda info --base 2>$null
    if ($condaBase) {
        $pythonPath = Join-Path $condaBase "envs\$condaEnv\python.exe"
        if (Test-Path $pythonPath) {
            Write-Host "Utilisation de Python depuis: $pythonPath" -ForegroundColor Gray
            Write-Host ""
            # Lancer directement avec le Python de l'environnement (sans conda run)
            & $pythonPath run_celery.py
        } else {
            Write-Host "Python de l'environnement conda non trouvé, utilisation de conda run..." -ForegroundColor Yellow
            Write-Host "Note: Ctrl+C peut ne pas fonctionner avec conda run" -ForegroundColor Yellow
            Write-Host "      Pour une meilleure gestion, utilisez directement: python run_celery.py" -ForegroundColor Cyan
            Write-Host ""
            & conda run -n $condaEnv python run_celery.py
        }
    } else {
        Write-Host "Impossible de trouver conda, utilisation de conda run..." -ForegroundColor Yellow
        Write-Host ""
        & conda run -n $condaEnv python run_celery.py
    }
} else {
    # Fallback vers la méthode classique si le wrapper n'existe pas
    Write-Host "Utilisation de la méthode classique..." -ForegroundColor Yellow
    Write-Host "Note: Ctrl+C peut ne pas fonctionner correctement avec cette méthode" -ForegroundColor Yellow
    Write-Host "      Utilisez 'python run_celery.py' pour une meilleure gestion de Ctrl+C" -ForegroundColor Cyan
    Write-Host ""
    
    try {
        & conda run -n $condaEnv celery -A celery_app worker --loglevel=info --pool=solo
    } catch {
        Write-Host "`nCelery arrêté." -ForegroundColor Yellow
    } finally {
        Write-Host "Nettoyage terminé." -ForegroundColor Green
    }
}

