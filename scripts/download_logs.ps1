# Script pour télécharger et analyser les logs depuis le serveur de production
# Usage: .\scripts\download_logs.ps1 [serveur] [utilisateur] [chemin]

param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'node15.lan',
    
    [Parameter(Mandatory=$false)]
    [string]$User = 'pi',
    
    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab'
)

$ErrorActionPreference = 'Stop'

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Téléchargement et analyse des logs" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Obtenir le répertoire du projet ProspectLab
$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$logsDir = Join-Path $PROJECT_DIR "logs_analysis"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logsArchive = Join-Path $logsDir "logs_$timestamp"

# Créer le répertoire d'analyse
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}
New-Item -ItemType Directory -Path $logsArchive -Force | Out-Null

Write-Host "[1/4] Vérification de la connexion SSH..." -ForegroundColor Yellow
try {
    $result = ssh -o ConnectTimeout=5 "$User@$Server" "echo 'Connexion OK'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Connexion échouée"
    }
    Write-Host "✅ Connexion SSH OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Impossible de se connecter au serveur" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Vérifier quels fichiers de logs existent
Write-Host "[2/4] Recherche des fichiers de logs..." -ForegroundColor Yellow
$logFiles = ssh "$User@$Server" "cd $RemotePath && find logs logs_server -type f -name '*.log' 2>/dev/null | head -20" 2>&1
if ($LASTEXITCODE -eq 0 -and $logFiles) {
    Write-Host "   Fichiers trouvés:" -ForegroundColor Gray
    $logFiles | ForEach-Object { Write-Host "     - $_" -ForegroundColor Gray }
} else {
    Write-Host "   Aucun fichier .log trouvé, recherche de tous les fichiers..." -ForegroundColor Gray
    $allFiles = ssh "$User@$Server" "cd $RemotePath && ls -la logs/ logs_server/ 2>/dev/null" 2>&1
    Write-Host $allFiles
}
Write-Host ""

# Créer une archive des logs sur le serveur
Write-Host "[3/4] Création d'une archive des logs sur le serveur..." -ForegroundColor Yellow
$remoteArchive = "/tmp/prospectlab_logs_$timestamp.tar.gz"
ssh "$User@$Server" "cd $RemotePath && tar -czf $remoteArchive logs/ logs_server/ 2>/dev/null || tar -czf $remoteArchive logs/ 2>/dev/null || echo 'Aucun log trouvé'" 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    # Télécharger l'archive
    Write-Host "   Téléchargement de l'archive..." -ForegroundColor Gray
    scp "$User@$Server`:$remoteArchive" "$logsArchive.tar.gz" 2>&1 | Out-Null
    
    if (Test-Path "$logsArchive.tar.gz") {
        # Extraire l'archive
        Write-Host "   Extraction de l'archive..." -ForegroundColor Gray
        tar -xzf "$logsArchive.tar.gz" -C $logsArchive 2>&1 | Out-Null
        
        # Nettoyer l'archive locale
        Remove-Item "$logsArchive.tar.gz" -Force -ErrorAction SilentlyContinue
        
        # Nettoyer l'archive sur le serveur
        ssh "$User@$Server" "rm -f $remoteArchive" 2>&1 | Out-Null
        
        Write-Host "✅ Logs téléchargés dans: $logsArchive" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Aucun log téléchargé (fichiers vides ou inexistants)" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️ Impossible de créer l'archive des logs" -ForegroundColor Yellow
}
Write-Host ""

# Analyser les logs
Write-Host "[4/4] Analyse des logs..." -ForegroundColor Yellow
$analysisFile = Join-Path $logsArchive "analysis_$timestamp.txt"

$analysis = @"
========================================
ANALYSE DES LOGS - $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
========================================

"@

# Trouver tous les fichiers de logs
$logFilesLocal = Get-ChildItem -Path $logsArchive -Recurse -File -ErrorAction SilentlyContinue

if ($logFilesLocal.Count -eq 0) {
    $analysis += "Aucun fichier de log trouvé dans l'archive.`n`n"
} else {
    $analysis += "Fichiers de logs trouvés: $($logFilesLocal.Count)`n"
    foreach ($file in $logFilesLocal) {
        $analysis += "  - $($file.FullName.Replace($logsArchive, '.'))`n"
    }
    $analysis += "`n"
    
    # Analyser chaque fichier
    foreach ($file in $logFilesLocal) {
        $analysis += "`n========================================`n"
        $analysis += "FICHIER: $($file.Name)`n"
        $analysis += "========================================`n`n"
        
        # Statistiques générales
        $content = Get-Content $file.FullName -ErrorAction SilentlyContinue
        $lineCount = ($content | Measure-Object -Line).Lines
        $fileSize = (Get-Item $file.FullName).Length
        
        $analysis += "Taille: $([math]::Round($fileSize/1KB, 2)) KB`n"
        $analysis += "Lignes: $lineCount`n`n"
        
        if ($lineCount -gt 0) {
            # Dernières lignes (erreurs récentes)
            $analysis += "--- DERNIÈRES 20 LIGNES ---`n"
            $lastLines = $content | Select-Object -Last 20
            $analysis += ($lastLines -join "`n")
            $analysis += "`n`n"
            
            # Recherche d'erreurs
            $errors = $content | Select-String -Pattern "ERROR|Error|error|Exception|Traceback|CRITICAL|Fatal" -CaseSensitive:$false
            if ($errors) {
                $analysis += "--- ERREURS TROUVÉES ($($errors.Count)) ---`n"
                $uniqueErrors = $errors | Select-Object -First 50 -Unique
                foreach ($err in $uniqueErrors) {
                    $analysis += "$err`n"
                }
                $analysis += "`n"
            }
            
            # Recherche d'avertissements
            $warnings = $content | Select-String -Pattern "WARNING|Warning|warning|WARN" -CaseSensitive:$false
            if ($warnings) {
                $analysis += "--- AVERTISSEMENTS TROUVÉS ($($warnings.Count)) ---`n"
                $uniqueWarnings = $warnings | Select-Object -First 30 -Unique
                foreach ($warn in $uniqueWarnings) {
                    $analysis += "$warn`n"
                }
                $analysis += "`n"
            }
            
            # Recherche de problèmes spécifiques
            $nanIssues = $content | Select-String -Pattern "NaN|nan|Not a Number" -CaseSensitive:$false
            if ($nanIssues) {
                $analysis += "--- PROBLÈMES NaN TROUVÉS ($($nanIssues.Count)) ---`n"
                foreach ($issue in $nanIssues) {
                    $analysis += "$issue`n"
                }
                $analysis += "`n"
            }
            
            # Recherche de problèmes JSON
            $jsonIssues = $content | Select-String -Pattern "JSON|json|SyntaxError|ParseError" -CaseSensitive:$false
            if ($jsonIssues) {
                $analysis += "--- PROBLÈMES JSON TROUVÉS ($($jsonIssues.Count)) ---`n"
                foreach ($issue in $jsonIssues) {
                    $analysis += "$issue`n"
                }
                $analysis += "`n"
            }
            
            # Statistiques par niveau de log
            $infoCount = ($content | Select-String -Pattern "INFO|Info" -CaseSensitive:$false).Count
            $debugCount = ($content | Select-String -Pattern "DEBUG|Debug" -CaseSensitive:$false).Count
            
            $analysis += "--- STATISTIQUES ---`n"
            $analysis += "Erreurs: $($errors.Count)`n"
            $analysis += "Avertissements: $($warnings.Count)`n"
            $analysis += "Infos: $infoCount`n"
            $analysis += "Debug: $debugCount`n`n"
        }
    }
}

# Sauvegarder l'analyse
$analysis | Out-File -FilePath $analysisFile -Encoding UTF8

Write-Host "✅ Analyse terminée" -ForegroundColor Green
Write-Host ""
Write-Host "Résultats:" -ForegroundColor Cyan
Write-Host "  Logs: $logsArchive" -ForegroundColor Yellow
Write-Host "  Analyse: $analysisFile" -ForegroundColor Yellow
Write-Host ""

# Afficher un résumé
Write-Host "--- RÉSUMÉ DE L'ANALYSE ---" -ForegroundColor Cyan
Get-Content $analysisFile -Head 50 | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Pour voir l'analyse complète:" -ForegroundColor Gray
Write-Host "  Get-Content `"$analysisFile`"" -ForegroundColor Gray
