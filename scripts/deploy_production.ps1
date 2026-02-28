# Script de déploiement ProspectLab en production
# Usage: .\scripts\deploy_production.ps1 [serveur] [utilisateur] [chemin]

param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'serveur-app.lan',
    
    [Parameter(Mandatory=$false)]
    [string]$User = 'deploy',
    
    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab',
    
    [Parameter(Mandatory=$false)]
    [string]$ProxyServer = '',
    
    [Parameter(Mandatory=$false)]
    [string]$ProxyUser = 'deploy'
)
# Usage: .\deploy_production.ps1 -Server serveur-app.lan -User deploy -ProxyServer serveur-proxy.lan -ProxyUser deploy

$ErrorActionPreference = 'Stop'

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Déploiement ProspectLab en production" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Obtenir le répertoire du projet ProspectLab (parent du dossier scripts)
$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName

# Vérifier la connexion SSH
Write-Host "[1/9] Vérification de la connexion SSH..." -ForegroundColor Yellow
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
Write-Host "[2/9] Préparation des fichiers locaux..." -ForegroundColor Yellow
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

# Vérifier Conda sur le serveur
Write-Host "[3/9] Vérification de Conda..." -ForegroundColor Yellow
$condaCheck = ssh "$User@$Server" "which conda 2>/dev/null || (source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null && which conda) || (source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null && which conda) || true" 2>$null
if (-not $condaCheck) {
    Write-Host "❌ Conda n'est pas installé sur le serveur (miniconda3 ou anaconda3)" -ForegroundColor Red
    Write-Host "   Installez Miniconda puis relancez le déploiement." -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Conda détecté" -ForegroundColor Green
Write-Host ""

# Créer le répertoire sur le serveur
Write-Host "[4/9] Préparation du répertoire sur le serveur..." -ForegroundColor Yellow
ssh "$User@$Server" "sudo mkdir -p $RemotePath && sudo chown -R $User`:$User $RemotePath" | Out-Null
Write-Host "✅ Répertoire créé sur le serveur" -ForegroundColor Green
Write-Host ""

# Copier les fichiers vers le serveur
Write-Host "[5/9] Transfert des fichiers vers le serveur..." -ForegroundColor Yellow
Write-Host "   Cela peut prendre quelques instants..." -ForegroundColor Gray

# Utiliser rsync si disponible (sauf sous Windows), sinon tar+scp pour éviter les problèmes de chemins
$useRsync = $false
try {
    $null = rsync --version 2>&1
    # On n'active rsync que si la commande existe ET que l'on n'est pas sur Windows
    if ($LASTEXITCODE -eq 0 -and $env:OS -ne 'Windows_NT') {
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

# Créer ou mettre à jour l'environnement Conda sur le serveur (prefix = env)
Write-Host "[6/9] Configuration de l'environnement Conda..." -ForegroundColor Yellow
$condaOutput = ssh "$User@$Server" "set -e; source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh; cd $RemotePath; if [ ! -d env ]; then conda create --prefix $RemotePath/env python=3.11 -y --override-channels -c conda-forge; fi; $RemotePath/env/bin/pip install --upgrade pip setuptools wheel; $RemotePath/env/bin/pip install -r requirements.txt" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors de l'installation des dépendances Conda/pip" -ForegroundColor Red
    Write-Host $condaOutput -ForegroundColor Gray
    exit 1
}
Write-Host "✅ Environnement Conda configuré (prefix=$RemotePath/env)" -ForegroundColor Green
Write-Host ""

# Créer les répertoires nécessaires
Write-Host "[7/9] Création des répertoires nécessaires..." -ForegroundColor Yellow
ssh "$User@$Server" "cd $RemotePath && mkdir -p logs logs_server" | Out-Null
Write-Host "✅ Répertoires créés" -ForegroundColor Green
Write-Host ""

# Ajouter les permissions d'exécution aux scripts shell
Write-Host "[7.5/9] Configuration des permissions des scripts..." -ForegroundColor Yellow
ssh "$User@$Server" "cd $RemotePath && find scripts/linux -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true" | Out-Null
ssh "$User@$Server" "cd $RemotePath && find scripts -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true" | Out-Null
Write-Host "✅ Permissions des scripts configurées" -ForegroundColor Green
Write-Host ""

# Mettre à jour les services systemd pour Conda (env)
Write-Host "[7.6/9] Mise à jour des services systemd (Conda)..." -ForegroundColor Yellow
$updateServices = ssh "$User@$Server" "test -x $RemotePath/scripts/linux/update_services_to_conda.sh && cd $RemotePath && sudo bash scripts/linux/update_services_to_conda.sh" 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host "✅ Services systemd mis à jour" -ForegroundColor Green } else { Write-Host "⚠️  Mise à jour des services ignorée (vérifiez sudo)" -ForegroundColor Yellow }
Write-Host ""

# Nettoyage du cache et redémarrage des services
Write-Host "[8/9] Nettoyage du cache et redémarrage des services..." -ForegroundColor Yellow
ssh "$User@$Server" "cd $RemotePath && if [ -x scripts/clear-cache.sh ]; then ./scripts/clear-cache.sh; fi" | Out-Null
ssh "$User@$Server" "sudo systemctl restart prospectlab prospectlab-celery prospectlab-celerybeat" | Out-Null
Write-Host "✅ Cache vidé et services redémarrés" -ForegroundColor Green
Write-Host ""

# Vérification que l'application répond sur le serveur app (évite 502 côté Nginx)
Write-Host "[8.5/9] Vérification de l'application sur $Server..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
$httpCode = ssh "$User@$Server" "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 http://127.0.0.1:5000/" 2>$null
if (-not $httpCode) { $httpCode = '000' }
if ($httpCode -eq '200' -or $httpCode -eq '302' -or $httpCode -eq '301') {
    Write-Host "✅ Application répond sur ${Server}:5000 (HTTP $httpCode)" -ForegroundColor Green
} else {
    Write-Host "⚠️  L'application ne répond pas correctement sur ${Server}:5000 (HTTP $httpCode)" -ForegroundColor Yellow
    Write-Host "   Sur le serveur app, vérifiez: sudo systemctl status prospectlab && curl -I http://127.0.0.1:5000/" -ForegroundColor Gray
    Write-Host "   Si Nginx affiche 502, vérifiez sur le serveur proxy que le serveur app est résolu et que le port 5000 est joignable." -ForegroundColor Gray
    Write-Host "   Voir: docs/configuration/DEPLOIEMENT_PRODUCTION.md (section Dépannage 502)" -ForegroundColor Gray
}
Write-Host ""

# Rechargement Nginx optionnel sur le serveur proxy
if ($ProxyServer) {
    Write-Host "[8.6/9] Rechargement Nginx sur le serveur proxy $ProxyServer..." -ForegroundColor Yellow
    $nginxReload = ssh -o ConnectTimeout=5 "$ProxyUser@$ProxyServer" "sudo nginx -t && sudo systemctl reload nginx" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Nginx rechargé sur $ProxyServer" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Impossible de recharger Nginx sur $ProxyServer (vérifiez SSH et sudo)" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Instructions finales
Write-Host "[9/9] Déploiement terminé !" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaines étapes:" -ForegroundColor Cyan
Write-Host "1. Connectez-vous au serveur de production" -ForegroundColor Yellow
Write-Host "2. Allez dans le répertoire de déploiement" -ForegroundColor Yellow
Write-Host "3. Configurez le fichier .env avec vos paramètres de production" -ForegroundColor Yellow
Write-Host "4. Environnement Conda: $RemotePath/env" -ForegroundColor Yellow
Write-Host "5. Initialisez la base de données si nécessaire" -ForegroundColor Yellow
Write-Host "6. Démarrez l'application (Gunicorn) ou vérifiez les services systemd" -ForegroundColor Yellow
Write-Host ""
Write-Host "Pour plus d'informations, consultez:" -ForegroundColor Cyan
Write-Host "  docs/configuration/DEPLOIEMENT_PRODUCTION.md" -ForegroundColor Gray
Write-Host ""

# Nettoyer le répertoire de déploiement local
Remove-Item -Recurse -Force $deployDir
Write-Host "✅ Répertoire de déploiement local nettoyé" -ForegroundColor Green
