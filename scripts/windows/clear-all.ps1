# Script PowerShell pour nettoyer TOUT: base de données, Redis et logs

param(
    [switch]$NoConfirm
)

# Gérer aussi les arguments Unix-style
$argsList = $args
foreach ($arg in $argsList) {
    if ($arg -eq "--no-confirm" -or $arg -eq "-no-confirm") {
        $NoConfirm = $true
    }
}

$ErrorActionPreference = "Stop"

# Déterminer le chemin du script Python
$scriptDir = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $scriptDir "clear_all.py"

# Convertir en chemin absolu
$pythonScript = (Resolve-Path $pythonScript -ErrorAction SilentlyContinue).Path
if (-not $pythonScript) {
    $pythonScript = Join-Path $scriptDir "clear_all.py"
}

# Vérifier que le script Python existe
if (-not (Test-Path $pythonScript)) {
    Write-Host "Erreur: Le script clear_all.py n'a pas été trouvé à: $pythonScript" -ForegroundColor Red
    exit 1
}

# Construire la commande Python
$pythonArgs = @()

if ($NoConfirm) {
    $pythonArgs += "--no-confirm"
}

# Essayer d'utiliser conda si disponible, sinon python
$pythonExe = "python"
$condaEnv = "prospectlab"

try {
    $condaCheck = conda env list 2>$null
    if ($condaCheck -match $condaEnv) {
        Write-Host "Utilisation de l'environnement Conda: $condaEnv" -ForegroundColor Cyan
        
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
Write-Host ""
Write-Host "NETTOYAGE COMPLET DE PROSPECTLAB" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
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

