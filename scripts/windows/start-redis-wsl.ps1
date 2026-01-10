# Script PowerShell pour démarrer Redis dans WSL

Write-Host "Démarrage de Redis dans WSL..." -ForegroundColor Green

# Vérifier si WSL est disponible
try {
    $wslVersion = wsl --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "WSL non disponible"
    }
} catch {
    Write-Host "ERREUR: WSL n'est pas disponible sur ce système." -ForegroundColor Red
    Write-Host "Installez WSL ou démarrez Docker Desktop pour utiliser Redis." -ForegroundColor Yellow
    exit 1
}

# Utiliser Ubuntu par défaut (ou kali-linux si configuré)
$wslDistro = "Ubuntu"

Write-Host "Vérification de Redis dans WSL ($wslDistro)..." -ForegroundColor Yellow

# Vérifier si Redis est installé
$redisInstalled = wsl -d $wslDistro -e bash -c "which redis-server" 2>&1

if ($LASTEXITCODE -ne 0 -or $redisInstalled -eq "") {
    Write-Host "Redis n'est pas installé. Installation en cours..." -ForegroundColor Yellow
    Write-Host "Cela peut prendre quelques minutes..." -ForegroundColor Cyan
    
    # Installer Redis dans WSL
    wsl -d $wslDistro -e bash -c "sudo apt-get update -qq && sudo apt-get install -y redis-server" 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERREUR: Impossible d'installer Redis dans WSL." -ForegroundColor Red
        Write-Host "Vérifiez que WSL est correctement configuré et que vous avez les droits administrateur." -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Redis a été installé avec succès." -ForegroundColor Green
} else {
    Write-Host "Redis est déjà installé." -ForegroundColor Green
}

# Configurer Redis pour écouter sur toutes les interfaces (nécessaire pour Windows)
Write-Host "Configuration de Redis pour l'accès depuis Windows..." -ForegroundColor Yellow
$bindConfig = wsl -d $wslDistro -e bash -c "sudo grep '^bind' /etc/redis/redis.conf 2>/dev/null" 2>&1

if ($bindConfig -notmatch "0\.0\.0\.0") {
    Write-Host "Modification de la configuration Redis..." -ForegroundColor Cyan
    wsl -d $wslDistro -e bash -c "sudo sed -i 's/^bind .*/bind 0.0.0.0/' /etc/redis/redis.conf" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Configuration Redis mise à jour." -ForegroundColor Green
    }
}

# Vérifier si Redis est déjà en cours d'exécution
$redisRunning = wsl -d $wslDistro -e bash -c "pgrep -x redis-server" 2>&1

if ($redisRunning -ne "") {
    Write-Host "Redis est déjà en cours d'exécution. Redémarrage pour appliquer la configuration..." -ForegroundColor Yellow
    wsl -d $wslDistro -e bash -c "sudo service redis-server restart" 2>&1 | Out-Null
} else {
    Write-Host "Démarrage de Redis..." -ForegroundColor Yellow
    
    # Démarrer Redis en arrière-plan dans WSL
    wsl -d $wslDistro -e bash -c "sudo service redis-server start" 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERREUR: Impossible de démarrer Redis." -ForegroundColor Red
        exit 1
    }
}

# Attendre que Redis soit prêt
Start-Sleep -Seconds 2

# Tester la connexion
Write-Host "Test de la connexion Redis..." -ForegroundColor Yellow
$result = wsl -d $wslDistro -e bash -c "redis-cli ping" 2>&1

if ($result -match "PONG") {
    Write-Host "`nRedis est démarré et fonctionne correctement!" -ForegroundColor Green
    Write-Host "Redis est accessible sur localhost:6379" -ForegroundColor Green
    Write-Host "`nNote: Redis tourne dans WSL ($wslDistro)" -ForegroundColor Cyan
} else {
    Write-Host "ERREUR: Redis ne répond pas correctement." -ForegroundColor Red
    Write-Host "Résultat du test: $result" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nPour arrêter Redis, utilisez: wsl -d $wslDistro -e bash -c 'sudo service redis-server stop'" -ForegroundColor Cyan
Write-Host "Pour voir le statut, utilisez: wsl -d $wslDistro -e bash -c 'sudo service redis-server status'" -ForegroundColor Cyan


