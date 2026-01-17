# Script PowerShell pour nettoyer les fichiers de logs de ProspectLab

param(
    [switch]$Clear,
    [switch]$NoConfirm,
    [switch]$Stats,
    [switch]$Delete,
    [string[]]$Files,
    [string]$LogsDir
)

# Gérer aussi les arguments Unix-style (--clear, --no-confirm, etc.)
$argsList = $args
foreach ($arg in $argsList) {
    if ($arg -eq "--clear" -or $arg -eq "-clear") {
        $Clear = $true
    }
    elseif ($arg -eq "--no-confirm" -or $arg -eq "-no-confirm") {
        $NoConfirm = $true
    }
    elseif ($arg -eq "--stats" -or $arg -eq "-stats") {
        $Stats = $true
    }
    elseif ($arg -eq "--delete" -or $arg -eq "-delete") {
        $Delete = $true
    }
    elseif ($arg -eq "--logs-dir" -or $arg -eq "-logs-dir") {
        $idx = [array]::IndexOf($argsList, $arg)
        if ($idx -ge 0 -and $idx -lt ($argsList.Length - 1)) {
            $LogsDir = $argsList[$idx + 1]
        }
    }
    elseif ($arg -eq "--files" -or $arg -eq "-files") {
        $idx = [array]::IndexOf($argsList, $arg)
        if ($idx -ge 0) {
            $Files = @()
            for ($i = $idx + 1; $i -lt $argsList.Length; $i++) {
                if ($argsList[$i] -match "^--" -or $argsList[$i] -match "^-") {
                    break
                }
                $Files += $argsList[$i]
            }
        }
    }
}

$ErrorActionPreference = "Stop"

# Déterminer le chemin du script Python
$scriptDir = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $scriptDir "clear_logs.py"

# Convertir en chemin absolu
$pythonScript = (Resolve-Path $pythonScript -ErrorAction SilentlyContinue).Path
if (-not $pythonScript) {
    $pythonScript = Join-Path $scriptDir "clear_logs.py"
}

# Vérifier que le script Python existe
if (-not (Test-Path $pythonScript)) {
    Write-Host "Erreur: Le script clear_logs.py n'a pas été trouvé à: $pythonScript" -ForegroundColor Red
    exit 1
}

# Construire la commande Python
$pythonArgs = @()

if ($Stats) {
    $pythonArgs += "--stats"
}

if ($Clear) {
    $pythonArgs += "--clear"
    
    if ($NoConfirm) {
        $pythonArgs += "--no-confirm"
    }
    
    if ($Delete) {
        $pythonArgs += "--delete"
    }
    
    if ($Files -and $Files.Count -gt 0) {
        $pythonArgs += "--files"
        foreach ($file in $Files) {
            $pythonArgs += $file
        }
    }
}

if ($LogsDir -and $LogsDir.Trim() -ne "") {
    $pythonArgs += "--logs-dir"
    $pythonArgs += $LogsDir.Trim()
}

# Essayer d'utiliser conda si disponible, sinon python
$pythonExe = "python"
$useConda = $false
$condaEnv = "prospectlab"

try {
    $condaCheck = conda env list 2>$null
    if ($condaCheck -match $condaEnv) {
        Write-Host "Utilisation de l'environnement Conda: $condaEnv" -ForegroundColor Cyan
        $useConda = $true
        
        $condaInfo = conda info --envs 2>$null
        $envLine = $condaInfo | Select-String $condaEnv
        if ($envLine) {
            $envPath = ($envLine -split '\s+')[1]
            if ($envPath) {
                $condaPython = Join-Path $envPath "python.exe"
                if (Test-Path $condaPython) {
                    $pythonExe = $condaPython
                }
            }
        }
    }
} catch {
    # Si conda n'est pas disponible, utiliser python directement
}

# Exécuter le script Python
Write-Host "Exécution du script de nettoyage des logs..." -ForegroundColor Cyan
Write-Host ""

try {
    $allArgs = @()
    $allArgs += $pythonScript
    
    foreach ($arg in $pythonArgs) {
        if ($arg) {
            $argStr = $arg.ToString().Trim()
            if ($argStr -ne "") {
                $allArgs += $argStr
            }
        }
    }
    
    & $pythonExe $allArgs
    
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        Write-Host "`nErreur lors de l'exécution du script Python (code: $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "Erreur: $_" -ForegroundColor Red
    Write-Host "Commande: $pythonExe $($allArgs -join ' ')" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Terminé!" -ForegroundColor Green

