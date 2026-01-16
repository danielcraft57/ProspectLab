# Script pour nettoyer Redis et arrêter toutes les tâches Celery en cours
# Utilise l'environnement conda prospectlab

Write-Host "Nettoyage de Redis..." -ForegroundColor Yellow

# Activer l'environnement conda prospectlab
$condaEnv = "prospectlab"
Write-Host "Activation de l'environnement conda: $condaEnv" -ForegroundColor Cyan

# Vérifier si conda est disponible
$condaCmd = Get-Command conda -ErrorAction SilentlyContinue

if ($condaCmd) {
    # Activer l'environnement et utiliser redis-cli depuis cet environnement
    $condaActivate = "conda activate $condaEnv"
    Write-Host "Utilisation de redis-cli depuis l'environnement conda..." -ForegroundColor Cyan
    
    # Essayer d'exécuter redis-cli via conda run
    $redisCliCmd = "conda run -n $condaEnv redis-cli FLUSHDB"
    try {
        Invoke-Expression $redisCliCmd | Out-Null
        Write-Host "✓ Redis nettoyé avec succès" -ForegroundColor Green
    } catch {
        # Si conda run ne fonctionne pas, essayer de trouver redis-cli dans l'environnement conda
        $condaPath = (conda info --envs | Select-String $condaEnv | ForEach-Object { $_.ToString().Split() | Select-Object -First 1 })
        if ($condaPath) {
            $redisCliPath = Join-Path $condaPath "Scripts\redis-cli.exe"
            if (Test-Path $redisCliPath) {
                Write-Host "Trouvé redis-cli dans l'environnement conda: $redisCliPath" -ForegroundColor Cyan
                & $redisCliPath FLUSHDB | Out-Null
                Write-Host "✓ Redis nettoyé avec succès" -ForegroundColor Green
            } else {
                Write-Host "⚠ redis-cli non trouvé dans l'environnement conda" -ForegroundColor Yellow
                Write-Host "Essaie de trouver redis-cli dans les emplacements courants..." -ForegroundColor Yellow
                
                $possiblePaths = @(
                    "C:\Program Files\Redis\redis-cli.exe",
                    "C:\redis\redis-cli.exe",
                    "$env:USERPROFILE\AppData\Local\Programs\Redis\redis-cli.exe"
                )
                
                $found = $false
                foreach ($path in $possiblePaths) {
                    if (Test-Path $path) {
                        Write-Host "Trouvé redis-cli à: $path" -ForegroundColor Cyan
                        & $path FLUSHDB | Out-Null
                        Write-Host "✓ Redis nettoyé avec succès" -ForegroundColor Green
                        $found = $true
                        break
                    }
                }
                
                if (-not $found) {
                    Write-Host "❌ redis-cli non trouvé" -ForegroundColor Red
                    Write-Host "Tu peux nettoyer Redis manuellement avec: python scripts/clear_redis.py" -ForegroundColor Yellow
                    Write-Host "Ou arrêter et redémarrer Redis" -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "⚠ Environnement conda $condaEnv non trouvé" -ForegroundColor Yellow
            Write-Host "Utilise: python scripts/clear_redis.py" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "⚠ conda non trouvé dans le PATH" -ForegroundColor Yellow
    Write-Host "Essaie de trouver redis-cli dans les emplacements courants..." -ForegroundColor Yellow
    
    $possiblePaths = @(
        "C:\Program Files\Redis\redis-cli.exe",
        "C:\redis\redis-cli.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Redis\redis-cli.exe"
    )
    
    $found = $false
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            Write-Host "Trouvé redis-cli à: $path" -ForegroundColor Cyan
            & $path FLUSHDB | Out-Null
            Write-Host "✓ Redis nettoyé avec succès" -ForegroundColor Green
            $found = $true
            break
        }
    }
    
    if (-not $found) {
        Write-Host "❌ redis-cli non trouvé" -ForegroundColor Red
        Write-Host "Tu peux nettoyer Redis manuellement avec: python scripts/clear_redis.py" -ForegroundColor Yellow
        Write-Host "Ou arrêter et redémarrer Redis" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Pour arrêter Celery, utilise: .\scripts\windows\stop-celery.ps1" -ForegroundColor Cyan
