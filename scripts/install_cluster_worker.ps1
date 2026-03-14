param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'node13.lan',

    [Parameter(Mandatory=$false)]
    [string]$User = 'pi',

    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab'
)

$ErrorActionPreference = 'Stop'

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Installation d'un worker Celery ProspectLab sur le cluster" -ForegroundColor Cyan
Write-Host "Serveur cible : $User@$Server" -ForegroundColor Cyan
Write-Host "Répertoire distant : $RemotePath" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Répertoire local du projet (parent de scripts/)
$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName

if (-not (Test-Path $PROJECT_DIR)) {
    Write-Host "[✗] Projet introuvable (PROJECT_DIR=$PROJECT_DIR)" -ForegroundColor Red
    exit 1
}

# 1) Vérifier la connexion SSH
Write-Host "[1/5] Vérification de la connexion SSH..." -ForegroundColor Yellow
try {
    $result = ssh -o ConnectTimeout=5 "$User@$Server" "echo 'Connexion OK'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Connexion échouée"
    }
    Write-Host "✅ Connexion SSH OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Impossible de se connecter à $User@$Server" -ForegroundColor Red
    Write-Host "   Vérifie que :" -ForegroundColor Yellow
    Write-Host "   - le Raspberry est allumé" -ForegroundColor Yellow
    Write-Host "   - SSH est activé (sudo raspi-config / ssh)" -ForegroundColor Yellow
    Write-Host "   - ta clé SSH est autorisée pour l'utilisateur $User" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# 2) Préparer un répertoire de déploiement local minimal
Write-Host "[2/5] Préparation des fichiers locaux (code + scripts)..." -ForegroundColor Yellow
$deployDir = Join-Path $PROJECT_DIR "deploy_cluster_worker"
if (Test-Path $deployDir) {
    Remove-Item -Recurse -Force $deployDir
}
New-Item -ItemType Directory -Path $deployDir | Out-Null

$itemsToCopy = @(
    'routes',
    'services',
    'tasks',
    'utils',
    'scripts',
    'celery_app.py',
    'config.py',
    'requirements.txt'
)

foreach ($item in $itemsToCopy) {
    $sourcePath = Join-Path $PROJECT_DIR $item
    if (Test-Path $sourcePath) {
        $destPath = Join-Path $deployDir $item
        Copy-Item -Recurse -Path $sourcePath -Destination $destPath
        Write-Host "  [+] $item" -ForegroundColor Green
    }
}

Write-Host "   Nettoyage des fichiers inutiles..." -ForegroundColor Gray
Get-ChildItem -Path $deployDir -Recurse -Force | Where-Object {
    $_.Name -eq '__pycache__' -or
    $_.Name -like '*.pyc' -or
    $_.Name -like '*.pyo' -or
    $_.Name -eq '.git' -or
    $_.Name -eq 'env' -or
    $_.Name -eq 'venv' -or
    $_.Name -like '*.db' -or
    $_.Name -like '*.log'
} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "✅ Fichiers prêts pour le worker" -ForegroundColor Green
Write-Host ""

# 3) Créer le répertoire distant et transférer les fichiers
Write-Host "[3/5] Préparation du répertoire distant et transfert..." -ForegroundColor Yellow
ssh "$User@$Server" "sudo mkdir -p $RemotePath && sudo chown -R $User`:$User $RemotePath" | Out-Null

$tempTar = Join-Path $env:TEMP "prospectlab_cluster_worker_$(Get-Random).tar"
$tempTarGz = "$tempTar.gz"

try {
    Push-Location $deployDir
    tar -czf $tempTarGz * 2>&1 | Out-Null

    if (-not (Test-Path $tempTarGz)) {
        Write-Host "❌ Impossible de créer l'archive temporaire" -ForegroundColor Red
        exit 1
    }

    scp $tempTarGz "$User@$Server`:/tmp/prospectlab_cluster_worker.tar.gz" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Erreur lors du transfert de l'archive vers le Raspberry" -ForegroundColor Red
        exit 1
    }

    ssh "$User@$Server" "cd $RemotePath && tar -xzf /tmp/prospectlab_cluster_worker.tar.gz && rm /tmp/prospectlab_cluster_worker.tar.gz" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Erreur lors de l'extraction de l'archive sur le Raspberry" -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
    if (Test-Path $tempTarGz) { Remove-Item $tempTarGz -Force -ErrorAction SilentlyContinue }
    if (Test-Path $tempTar) { Remove-Item $tempTar -Force -ErrorAction SilentlyContinue }
}

Write-Host "✅ Code synchronisé dans $RemotePath sur $Server" -ForegroundColor Green
Write-Host ""

# 3.5) Forcer la synchro des scripts Linux modifiés (install_all_tools, trixie, etc.) via scp
Write-Host "[3.5/5] Synchronisation explicite des scripts Linux récents..." -ForegroundColor Yellow

ssh "$User@$Server" "mkdir -p $RemotePath/scripts/linux; mkdir -p $RemotePath/scripts/linux/trixie" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de préparer $RemotePath/scripts/linux sur $Server" -ForegroundColor Red
    exit 1
}

$linuxScriptsToCopy = @(
    'scripts\linux\install_all_tools.sh',
    'scripts\linux\install_osint_tools_kali.sh',
    'scripts\linux\install_pentest_tools_kali.sh',
    'scripts\linux\trixie\install_osint_tools_trixie.sh',
    'scripts\linux\trixie\install_pentest_tools_trixie.sh',
    'scripts\linux\trixie\install_seo_tools_trixie.sh',
    'scripts\linux\trixie\install_social_tools_trixie.sh'
)

foreach ($relPath in $linuxScriptsToCopy) {
    $localPath = Join-Path $PROJECT_DIR $relPath
    if (-not (Test-Path $localPath)) {
        continue
    }
    $remoteDir =
        if ($relPath -like 'scripts\linux\trixie\*') { "$RemotePath/scripts/linux/trixie/" }
        else { "$RemotePath/scripts/linux/" }
    scp $localPath "$User@$Server`:$remoteDir" 2>&1 | Out-Null
}

Write-Host "✅ Scripts Linux mis à jour sur $Server" -ForegroundColor Green
Write-Host ""

# 4) Rendre les scripts exécutables et lancer le script d'installation Linux
Write-Host "[4/5] Execution du script d'installation du worker sur le Raspberry..." -ForegroundColor Yellow

$remoteScriptPath = "$RemotePath/scripts/linux/install_cluster_worker.sh"

# Toujours pousser la dernière version du script d'installation Linux via scp
ssh "$User@$Server" "mkdir -p $RemotePath/scripts/linux" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de créer $RemotePath/scripts/linux sur $Server (vérifie les permissions)" -ForegroundColor Red
    exit 1
}

$localInstallScript = Join-Path $PROJECT_DIR "scripts\linux\install_cluster_worker.sh"
if (-not (Test-Path $localInstallScript)) {
    Write-Host "❌ Script local introuvable: $localInstallScript" -ForegroundColor Red
    exit 1
}

Write-Host "   Copie de install_cluster_worker.sh vers le Raspberry via scp..." -ForegroundColor Gray
scp $localInstallScript "$User@$Server`:$RemotePath/scripts/linux/" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de copier install_cluster_worker.sh sur $Server" -ForegroundColor Red
    exit 1
}

# Donner les droits d'exécution puis lancer le script côté Raspberry
ssh "$User@$Server" "cd $RemotePath; chmod +x scripts/linux/*.sh 2>/dev/null || true; bash scripts/linux/install_cluster_worker.sh" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors de l'exécution de install_cluster_worker.sh sur $Server" -ForegroundColor Red
    Write-Host "   Vérifie les logs affichés ci-dessus." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Script d'installation du worker exécuté avec succès" -ForegroundColor Green
Write-Host ""

# 5) Rappel pour le .env et le démarrage du service
Write-Host "[5/5] Étapes restantes manuelles importantes" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Sur le master (node15.lan), copie ton .env vers le worker :" -ForegroundColor Cyan
Write-Host "   ssh pi@node15.lan 'cat /opt/prospectlab/.env' > .env.master" -ForegroundColor Gray
Write-Host "   scp .env.master $User@$Server`:$RemotePath/.env" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Sur le worker ($Server), adapte au minimum dans $RemotePath/.env :" -ForegroundColor Cyan
Write-Host "   - CELERY_BROKER_URL=redis://node15.lan:6379/1" -ForegroundColor Gray
Write-Host "   - CELERY_RESULT_BACKEND=redis://node15.lan:6379/1" -ForegroundColor Gray
Write-Host "   - DATABASE_URL=postgresql://prospectlab:TON_MDP@node15.lan:5432/prospectlab" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Ensuite démarre le service worker sur le Raspberry :" -ForegroundColor Cyan
Write-Host "   ssh $User@$Server 'sudo systemctl enable prospectlab-celery && sudo systemctl start prospectlab-celery && sudo systemctl status prospectlab-celery'" -ForegroundColor Gray
Write-Host ""
Write-Host "Installation du worker Celery terminée côté Windows pour $Server." -ForegroundColor Green

# Nettoyage du répertoire de déploiement local
Remove-Item -Recurse -Force $deployDir
Write-Host "✅ Répertoire de préparation locale nettoyé" -ForegroundColor Green

