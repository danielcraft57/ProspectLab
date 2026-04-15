# Script pour nettoyer Redis et arrêter toutes les tâches Celery en cours
# Utilise l'environnement conda prospectlab

Write-Host "Nettoyage de Redis..." -ForegroundColor Yellow

$redisFlushed = $false

function Invoke-RedisFlush {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    try {
        $output = & $Command @Arguments 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        if ($output) {
            Write-Host ($output | Out-String).Trim() -ForegroundColor DarkYellow
        }
        return $false
    } catch {
        Write-Host ("Echec execution: " + $_.Exception.Message) -ForegroundColor DarkYellow
        return $false
    }
}

function Invoke-CondaPythonClear {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CondaEnv
    )

    try {
        Write-Host "Tentative fallback via python conda..." -ForegroundColor Cyan
        $output = conda run -n $CondaEnv python scripts/clear_redis.py 2>&1
        if ($output) {
            Write-Host ($output | Out-String).Trim()
        }
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        return $false
    } catch {
        Write-Host ("Fallback python conda en echec: " + $_.Exception.Message) -ForegroundColor DarkYellow
        return $false
    }
}

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
        if ($LASTEXITCODE -eq 0) {
            $redisFlushed = $true
            Write-Host "Redis nettoye avec succes" -ForegroundColor Green
        } else {
            throw "conda run redis-cli a retourne le code $LASTEXITCODE"
        }
    } catch {
        # Si conda run ne fonctionne pas, essayer de trouver redis-cli dans l'environnement conda
        $condaPath = (conda info --envs | Select-String $condaEnv | ForEach-Object { $_.ToString().Split() | Select-Object -First 1 })
        if ($condaPath) {
            $redisCliPath = Join-Path $condaPath "Scripts\redis-cli.exe"
            if (Test-Path $redisCliPath) {
                Write-Host "Trouvé redis-cli dans l'environnement conda: $redisCliPath" -ForegroundColor Cyan
                if (Invoke-RedisFlush -Command $redisCliPath -Arguments @("FLUSHDB")) {
                    $redisFlushed = $true
                    Write-Host "Redis nettoye avec succes" -ForegroundColor Green
                }
            } else {
                Write-Host "redis-cli non trouve dans l'environnement conda" -ForegroundColor Yellow
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
                        if (Invoke-RedisFlush -Command $path -Arguments @("FLUSHDB")) {
                            Write-Host "Redis nettoye avec succes" -ForegroundColor Green
                            $found = $true
                            $redisFlushed = $true
                        }
                        break
                    }
                }
                
                if (-not $found) {
                    Write-Host "redis-cli non trouve" -ForegroundColor Red
                    Write-Host "Tu peux nettoyer Redis manuellement avec: python scripts/clear_redis.py" -ForegroundColor Yellow
                    Write-Host "Ou arreter et redemarrer Redis" -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "Environnement conda $condaEnv non trouve" -ForegroundColor Yellow
            Write-Host "Utilise: python scripts/clear_redis.py" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "conda non trouve dans le PATH" -ForegroundColor Yellow
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
            if (Invoke-RedisFlush -Command $path -Arguments @("FLUSHDB")) {
                Write-Host "Redis nettoye avec succes" -ForegroundColor Green
                $found = $true
                $redisFlushed = $true
            }
            break
        }
    }
    
    if (-not $found) {
        Write-Host "redis-cli non trouve" -ForegroundColor Red
        Write-Host "Tu peux nettoyer Redis manuellement avec: python scripts/clear_redis.py" -ForegroundColor Yellow
        Write-Host "Ou arreter et redemarrer Redis" -ForegroundColor Yellow
    }
}

if (-not $redisFlushed) {
    if ($condaCmd) {
        if (Invoke-CondaPythonClear -CondaEnv $condaEnv) {
            $redisFlushed = $true
            Write-Host "Redis nettoye avec succes (fallback python conda)." -ForegroundColor Green
        }
    }
}

if (-not $redisFlushed) {
    Write-Host "Redis n'a pas ete nettoye automatiquement." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Pour arreter Celery, utilise: .\scripts\windows\stop-celery.ps1" -ForegroundColor Cyan
