# Script PowerShell pour démarrer Redis avec Docker

Write-Host "Démarrage de Redis avec Docker..." -ForegroundColor Green

# Vérifier si Docker est en cours d'exécution
Write-Host "Vérification de Docker..." -ForegroundColor Yellow
try {
    $null = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker non accessible"
    }
} catch {
    Write-Host "`nERREUR: Docker Desktop n'est pas démarré!" -ForegroundColor Red
    Write-Host "`nÉtapes à suivre:" -ForegroundColor Yellow
    Write-Host "1. Ouvre Docker Desktop depuis le menu Démarrer" -ForegroundColor Cyan
    Write-Host "2. Attends que Docker Desktop soit complètement démarré (icône dans la barre des tâches)" -ForegroundColor Cyan
    Write-Host "3. Relance ce script: .\start-redis.ps1" -ForegroundColor Cyan
    Write-Host "`nOu démarre Docker Desktop manuellement puis relance ce script." -ForegroundColor Yellow
    exit 1
}
Write-Host "Docker est accessible." -ForegroundColor Green

# Vérifier si le conteneur existe déjà
$containerExists = docker ps -a --filter "name=prospectlab-redis" --format "{{.Names}}"

if ($containerExists -eq "prospectlab-redis") {
    Write-Host "Le conteneur Redis existe déjà. Démarrage..." -ForegroundColor Yellow
    docker start prospectlab-redis
} else {
    Write-Host "Création et démarrage du conteneur Redis..." -ForegroundColor Yellow
    docker-compose up -d
}

# Attendre que Redis soit prêt
Write-Host "Attente que Redis soit prêt..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

# Tester la connexion
try {
    $result = docker exec prospectlab-redis redis-cli ping
    if ($result -eq "PONG") {
        Write-Host "Redis est démarré et fonctionne correctement!" -ForegroundColor Green
        Write-Host "Redis est accessible sur localhost:6379" -ForegroundColor Green
    } else {
        Write-Host "Redis a démarré mais ne répond pas correctement." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Impossible de tester Redis. Vérifiez manuellement avec: docker exec prospectlab-redis redis-cli ping" -ForegroundColor Yellow
}

Write-Host "`nPour arrêter Redis, utilisez: docker stop prospectlab-redis" -ForegroundColor Cyan
Write-Host "Pour voir les logs, utilisez: docker logs prospectlab-redis" -ForegroundColor Cyan

