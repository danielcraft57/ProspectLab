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
Write-Host "Démarrage de Celery worker avec Beat (tâches périodiques)..." -ForegroundColor Yellow
Write-Host "  - Worker: exécute les tâches asynchrones" -ForegroundColor Cyan
Write-Host "  - Beat: exécute les tâches périodiques (nettoyage toutes les heures)" -ForegroundColor Cyan
Write-Host "Appuyez sur Ctrl+C pour arrêter Celery" -ForegroundColor Cyan
Write-Host ""

# Option pour effacer les logs au démarrage
# Décommentez les lignes suivantes si vous voulez effacer les logs à chaque démarrage
# if (Test-Path "logs\celery.log") { Remove-Item "logs\celery.log" -Force; Write-Host "Log Celery effacé" -ForegroundColor Yellow }
# if (Test-Path "logs\*.log") { Remove-Item "logs\*.log" -Force; Write-Host "Tous les logs effacés" -ForegroundColor Yellow }

Write-Host "Logs disponibles dans le dossier: logs\" -ForegroundColor Cyan
Write-Host "  - celery_worker.log : Logs du worker Celery" -ForegroundColor Gray
Write-Host "  - celery_beat.log : Logs du beat scheduler (tâches périodiques)" -ForegroundColor Gray
Write-Host "  - prospectlab.log : Logs de l'application Flask" -ForegroundColor Gray
Write-Host "  - *.log : Logs des différentes tâches" -ForegroundColor Gray
Write-Host ""

# Activer l'environnement conda et lancer Celery
$condaEnv = "prospectlab"
$useConda = $false
$pythonExe = "python"

# Vérifier si conda est disponible et si l'environnement existe
try {
    $condaCheck = conda env list 2>$null
    if ($condaCheck -match $condaEnv) {
        Write-Host "Utilisation de l'environnement Conda: $condaEnv" -ForegroundColor Cyan
        $useConda = $true
        
        # Trouver le chemin Python dans l'environnement conda
        $condaBase = & conda info --base 2>$null
        if ($condaBase) {
            $condaPython = Join-Path $condaBase "envs\$condaEnv\python.exe"
            if (Test-Path $condaPython) {
                $pythonExe = $condaPython
                Write-Host "Python de l'environnement: $pythonExe" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "Avertissement: L'environnement conda '$condaEnv' n'a pas été trouvé" -ForegroundColor Yellow
        Write-Host "Utilisation de Python système..." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Avertissement: Conda n'est pas disponible, utilisation de Python système..." -ForegroundColor Yellow
}

Write-Host ""

# Lancer Celery avec le mode solo pour Windows
Write-Host "Lancement de Celery (mode solo pour Windows)..." -ForegroundColor Green
Write-Host "Note: Pour arrêter Celery, utilisez Ctrl+C ou le script stop-celery.ps1" -ForegroundColor Cyan
Write-Host ""

# Fonction pour arrêter les processus Celery
function Stop-CeleryProcesses {
    Write-Host "`nArrêt des processus Celery en arrière-plan..." -ForegroundColor Yellow
    
    # Fonction pour obtenir la ligne de commande d'un processus
    function Get-ProcessCommandLine {
        param([int]$ProcessId)
        try {
            $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
            return $process.CommandLine
        } catch {
            return $null
        }
    }
    
    # Trouver tous les processus Python
    $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
    $celeryProcesses = @()
    
    # Filtrer les processus qui exécutent Celery
    foreach ($proc in $pythonProcesses) {
        $commandLine = Get-ProcessCommandLine -ProcessId $proc.Id
        if ($commandLine) {
            # Vérifier si c'est un processus Celery
            if ($commandLine -match "celery.*worker" -or 
                $commandLine -match "celery.*beat" -or 
                $commandLine -match "run_celery\.py" -or
                $commandLine -match "celery_app") {
                $celeryProcesses += $proc
            }
        }
    }
    
    if ($celeryProcesses.Count -gt 0) {
        foreach ($proc in $celeryProcesses) {
            try {
                Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            } catch {
                # Ignorer les erreurs si le processus est déjà arrêté
            }
        }
        Write-Host "  ✓ $($celeryProcesses.Count) processus Celery arrêtés" -ForegroundColor Green
    }
}

# Utiliser le wrapper Python pour une meilleure gestion de Ctrl+C
if (Test-Path "run_celery.py") {
    Write-Host "Utilisation du wrapper Python pour une meilleure gestion de Ctrl+C..." -ForegroundColor Cyan
    Write-Host ""
    
    # Configurer le gestionnaire pour Ctrl+C
    [Console]::TreatControlCAsInput = $false
    
    try {
        # Lancer directement avec le Python configuré (conda ou système)
        & $pythonExe run_celery.py
    } catch {
        # Si erreur, arrêter les processus
        Write-Host "`nErreur détectée, arrêt des processus..." -ForegroundColor Yellow
        Stop-CeleryProcesses
    } finally {
        # S'assurer que tous les processus sont arrêtés
        Write-Host "`nNettoyage des processus en arrière-plan..." -ForegroundColor Yellow
        Stop-CeleryProcesses
    }
} else {
    # Fallback vers la méthode classique si le wrapper n'existe pas
    Write-Host "Utilisation de la méthode classique..." -ForegroundColor Yellow
    Write-Host "Note: Ctrl+C peut ne pas fonctionner correctement avec cette méthode" -ForegroundColor Yellow
    Write-Host "      Utilisez 'python run_celery.py' pour une meilleure gestion de Ctrl+C" -ForegroundColor Cyan
    Write-Host ""
    
    try {
        if ($useConda) {
            & conda run -n $condaEnv celery -A celery_app worker --loglevel=info --pool=threads --concurrency=4 --beat
        } else {
            & celery -A celery_app worker --loglevel=info --pool=threads --concurrency=4 --beat
        }
    } catch {
        Write-Host "`nCelery arrêté." -ForegroundColor Yellow
    } finally {
        Write-Host "Nettoyage terminé." -ForegroundColor Green
        Stop-CeleryProcesses
    }
}

