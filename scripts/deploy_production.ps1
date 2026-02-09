# Script de déploiement ProspectLab en production
# Usage: .\scripts\deploy_production.ps1 [serveur] [utilisateur] [chemin]

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
Write-Host "Déploiement ProspectLab en production" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Obtenir le répertoire du projet ProspectLab (parent du dossier scripts)
$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName

# Vérifier la connexion SSH
Write-Host "[1/8] Vérification de la connexion SSH..." -ForegroundColor Yellow
try {
    $result = ssh -o ConnectTimeout=5 "$User@$Server" "echo 'Connexion OK'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Connexion échouée"
    }
    Write-Host "✅ Connexion SSH OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Impossible de se connecter au serveur" -ForegroundColor Red
    Write-Host "   Vérifiez que:" -ForegroundColor Yellow
    Write-Host "   - Le serveur est allumé" -ForegroundColor Yellow
    Write-Host "   - SSH est activé" -ForegroundColor Yellow
    Write-Host "   - La clé SSH est configurée" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Créer le répertoire de déploiement local
Write-Host "[2/8] Préparation des fichiers locaux..." -ForegroundColor Yellow
$deployDir = Join-Path $PROJECT_DIR "deploy"
if (Test-Path $deployDir) {
    Remove-Item -Recurse -Force $deployDir
}
New-Item -ItemType Directory -Path $deployDir | Out-Null

# Copier les fichiers nécessaires
$filesToCopy = @(
    'routes',
    'services',
    'tasks',
    'templates',
    'static',
    'utils',
    'scripts',
    'app.py',
    'celery_app.py',
    'config.py',
    'requirements.txt',
    'README.md',
    'run_celery.py'
)

# Vérifier que templates/pages existe et sera copié avec templates
Write-Host "   Vérification des templates/pages..." -ForegroundColor Gray
$templatesPagesPath = Join-Path $PROJECT_DIR "templates\pages"
if (Test-Path $templatesPagesPath) {
    Write-Host "  [+] templates/pages détecté" -ForegroundColor Green
}

Write-Host "   Copie des fichiers..." -ForegroundColor Gray
foreach ($item in $filesToCopy) {
    $sourcePath = Join-Path $PROJECT_DIR $item
    if (Test-Path $sourcePath) {
        $destPath = Join-Path $deployDir $item
        Copy-Item -Recurse -Path $sourcePath -Destination $destPath
        Write-Host "  [+] $item" -ForegroundColor Green
        
        # Vérifications supplémentaires pour les dossiers importants
        if ($item -eq 'templates') {
            $pagesPath = Join-Path $destPath "pages"
            if (Test-Path $pagesPath) {
                $pageCount = (Get-ChildItem -Path $pagesPath -Filter "*.html" -Recurse -ErrorAction SilentlyContinue).Count
                Write-Host "     └─ templates/pages/ : $pageCount fichiers HTML" -ForegroundColor Gray
            }
        }
        if ($item -eq 'static') {
            $jsPath = Join-Path $destPath "js"
            $cssPath = Join-Path $destPath "css"
            $jsCount = if (Test-Path $jsPath) { (Get-ChildItem -Path $jsPath -Filter "*.js" -Recurse -ErrorAction SilentlyContinue).Count } else { 0 }
            $cssCount = if (Test-Path $cssPath) { (Get-ChildItem -Path $cssPath -Filter "*.css" -Recurse -ErrorAction SilentlyContinue).Count } else { 0 }
            Write-Host "     └─ static/ : $jsCount fichiers JS, $cssCount fichiers CSS" -ForegroundColor Gray
        }
    }
}

# Exclure les fichiers inutiles
Write-Host "   Nettoyage des fichiers inutiles..." -ForegroundColor Gray
$excludePatterns = @(
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '.git',
    'venv',
    'env',
    '.env',
    '*.db',
    '*.log',
    'deploy',
    'logs',
    'logs_server',
    '.cursorrules'
)

# Exclure par nom de dossier pour deploy/logs (éviter de matcher le chemin .../deploy/...)
$excludeDirNames = @('deploy', 'logs', 'logs_server')
Get-ChildItem -Path $deployDir -Recurse -Force | Where-Object {
    $exclude = $false
    foreach ($pattern in $excludePatterns) {
        if ($pattern -in $excludeDirNames) {
            if ($_.Name -eq $pattern) { $exclude = $true; break }
        } elseif ($_.FullName -like "*$pattern*") {
            $exclude = $true
            break
        }
    }
    return $exclude
} | Remove-Item -Recurse -Force

Write-Host "✅ Fichiers préparés" -ForegroundColor Green
Write-Host ""

# Vérifier Python sur le serveur
Write-Host "[3/8] Vérification de Python..." -ForegroundColor Yellow
$pythonVersion = ssh "$User@$Server" "python3 --version 2>&1" | Select-Object -First 1
if (-not $pythonVersion) {
    Write-Host "❌ Python3 n'est pas installé sur le serveur" -ForegroundColor Red
    exit 1
}
Write-Host "✅ $pythonVersion détecté" -ForegroundColor Green
Write-Host ""

# Créer le répertoire sur le serveur
Write-Host "[4/8] Préparation du répertoire sur le serveur..." -ForegroundColor Yellow
ssh "$User@$Server" "sudo mkdir -p $RemotePath && sudo chown -R $User`:$User $RemotePath" | Out-Null
Write-Host "✅ Répertoire créé sur le serveur" -ForegroundColor Green
Write-Host ""

# Copier les fichiers vers le serveur
Write-Host "[5/8] Transfert des fichiers vers le serveur..." -ForegroundColor Yellow
Write-Host "   Cela peut prendre quelques instants..." -ForegroundColor Gray

# Utiliser rsync si disponible, sinon tar+scp pour éviter les problèmes de chemins Windows
$useRsync = $false
try {
    $null = rsync --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $useRsync = $true
    }
} catch {
    $useRsync = $false
}

if ($useRsync) {
    # Utiliser rsync pour un transfert plus fiable et synchroniser les suppressions
    rsync -avz --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' "$deployDir/" "$User@$Server`:$RemotePath/" 2>&1 | Out-Null
    $transferSuccess = ($LASTEXITCODE -eq 0)
} else {
    # Utiliser tar+scp pour éviter les problèmes de chemins Windows
    $tempTar = Join-Path $env:TEMP "prospectlab_deploy_$(Get-Random).tar"
    $tempTarGz = "$tempTar.gz"
    
    try {
        Push-Location $deployDir
        tar -czf $tempTarGz * 2>&1 | Out-Null
        
        if (Test-Path $tempTarGz) {
            scp $tempTarGz "$User@$Server`:/tmp/prospectlab_deploy.tar.gz" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                # Extraire l'archive. Pas de suppression préalable: on évite de casser le serveur si le transfert échoue.
                ssh "$User@$Server" "cd $RemotePath && tar -xzf /tmp/prospectlab_deploy.tar.gz && rm /tmp/prospectlab_deploy.tar.gz" 2>&1 | Out-Null
                $transferSuccess = ($LASTEXITCODE -eq 0)
            } else {
                $transferSuccess = $false
            }
            Remove-Item $tempTarGz -Force -ErrorAction SilentlyContinue
        } else {
            # Fallback: scp classique fichier par fichier
            Write-Host "   Utilisation de la méthode de transfert alternative..." -ForegroundColor Gray
            $items = Get-ChildItem -Path $deployDir
            $transferSuccess = $true
            foreach ($item in $items) {
                $itemName = $item.Name
                scp -r "$deployDir\$itemName" "$User@$Server`:$RemotePath/" 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    $transferSuccess = $false
                    break
                }
            }
        }
    } finally {
        Pop-Location
        if (Test-Path $tempTar) { Remove-Item $tempTar -Force -ErrorAction SilentlyContinue }
        if (Test-Path $tempTarGz) { Remove-Item $tempTarGz -Force -ErrorAction SilentlyContinue }
    }
}

if (-not $transferSuccess) {
    Write-Host "❌ Erreur lors du transfert des fichiers" -ForegroundColor Red
    Write-Host "   Vérifiez les permissions et la connexion SSH" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Fichiers transférés" -ForegroundColor Green

# Envoi explicite de chaque dossier (garantit leur présence, notamment si tar sous Windows mal extrait)
$dirsToSync = @('routes', 'services', 'tasks', 'templates', 'static', 'utils', 'scripts')
foreach ($dir in $dirsToSync) {
    $dirPath = Join-Path $deployDir $dir
    if (Test-Path $dirPath -PathType Container) {
        Write-Host "   Envoi de $dir..." -ForegroundColor Gray
        scp -r "$dirPath" "$User@$Server`:$RemotePath/" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Host "❌ Erreur envoi $dir" -ForegroundColor Red; exit 1 }
    }
}
Write-Host "✅ Dossiers synchronisés (routes, services, tasks, templates, static, utils, scripts)" -ForegroundColor Green
Write-Host ""

# Créer l'environnement virtuel sur le serveur
Write-Host "[6/8] Configuration de l'environnement virtuel..." -ForegroundColor Yellow
ssh "$User@$Server" "cd $RemotePath && if [ ! -d venv ]; then python3 -m venv venv; fi" | Out-Null
ssh "$User@$Server" "cd $RemotePath && source venv/bin/activate && pip install --upgrade pip setuptools wheel && pip install -r requirements.txt" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors de l'installation des dépendances" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Environnement virtuel configuré" -ForegroundColor Green
Write-Host ""

# Créer les répertoires nécessaires
Write-Host "[7/8] Création des répertoires nécessaires..." -ForegroundColor Yellow
ssh "$User@$Server" "cd $RemotePath && mkdir -p logs logs_server" | Out-Null
Write-Host "✅ Répertoires créés" -ForegroundColor Green
Write-Host ""

# Ajouter les permissions d'exécution aux scripts shell
Write-Host "[7.5/8] Configuration des permissions des scripts..." -ForegroundColor Yellow
ssh "$User@$Server" "cd $RemotePath && find scripts/linux -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true" | Out-Null
ssh "$User@$Server" "cd $RemotePath && find scripts -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true" | Out-Null
Write-Host "✅ Permissions des scripts configurées" -ForegroundColor Green
Write-Host ""

# Instructions finales
Write-Host "[8/8] Déploiement terminé !" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaines étapes:" -ForegroundColor Cyan
Write-Host "1. Connectez-vous au serveur de production" -ForegroundColor Yellow
Write-Host "2. Allez dans le répertoire de déploiement" -ForegroundColor Yellow
Write-Host "3. Configurez le fichier .env avec vos paramètres de production" -ForegroundColor Yellow
Write-Host "4. Activez l'environnement virtuel: source venv/bin/activate" -ForegroundColor Yellow
Write-Host "5. Initialisez la base de données si nécessaire" -ForegroundColor Yellow
Write-Host "6. Démarrez l'application avec Gunicorn ou configurez un service systemd" -ForegroundColor Yellow
Write-Host ""
Write-Host "Pour plus d'informations, consultez:" -ForegroundColor Cyan
Write-Host "  docs/configuration/DEPLOIEMENT_PRODUCTION.md" -ForegroundColor Gray
Write-Host ""

# Nettoyer le répertoire de déploiement local
Remove-Item -Recurse -Force $deployDir
Write-Host "✅ Répertoire de déploiement local nettoyé" -ForegroundColor Green
