param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'worker1.lan',

    [Parameter(Mandatory=$false)]
    [string]$User = 'deploy',

    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$MasterServer = 'master.lan',

    [Parameter(Mandatory=$false)]
    [string]$MasterUser = 'deploy',

    [Parameter(Mandatory=$false)]
    [string]$MasterRemotePath = '/opt/prospectlab'
)

$ErrorActionPreference = 'Stop'

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test d'un worker Celery ProspectLab sur le cluster" -ForegroundColor Cyan
Write-Host "Serveur : $User@$Server" -ForegroundColor Cyan
Write-Host "Répertoire distant : $RemotePath" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Vérification de la connexion SSH..." -ForegroundColor Yellow
try {
    $null = ssh -o ConnectTimeout=5 "$User@$Server" "echo 'Connexion OK'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Connexion échouée"
    }
    Write-Host "✅ Connexion SSH OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Impossible de se connecter à $User@$Server" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "[2/3] Lancement du script de test côté Raspberry..." -ForegroundColor Yellow
$remoteScript = "$RemotePath/scripts/linux/test_cluster_worker.sh"

# Toujours pousser les fichiers nécessaires avant le test (évite les décalages de version)
Write-Host "   Synchronisation des fichiers de test via scp..." -ForegroundColor Gray

ssh "$User@$Server" "mkdir -p $RemotePath/scripts/linux; mkdir -p $RemotePath/scripts/linux/trixie; mkdir -p $RemotePath/tasks" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de créer les dossiers sur $Server (vérifie les permissions sur $RemotePath)" -ForegroundColor Red
    exit 1
}

$projectRoot = (Split-Path -Parent $PSScriptRoot)
$filesToCopy = @(
    @{ Local = (Join-Path $projectRoot "scripts\linux\test_cluster_worker.sh"); RemoteDir = "$RemotePath/scripts/linux/" },
    @{ Local = (Join-Path $projectRoot "scripts\linux\test_all_tools.sh"); RemoteDir = "$RemotePath/scripts/linux/" },
    @{ Local = (Join-Path $projectRoot "scripts\linux\trixie\test_all_tools_trixie.sh"); RemoteDir = "$RemotePath/scripts/linux/trixie/" },
    @{ Local = (Join-Path $projectRoot "scripts\linux\trixie\test_osint_tools_prod.sh"); RemoteDir = "$RemotePath/scripts/linux/trixie/" },
    @{ Local = (Join-Path $projectRoot "scripts\linux\trixie\test_pentest_tools_prod.sh"); RemoteDir = "$RemotePath/scripts/linux/trixie/" },
    @{ Local = (Join-Path $projectRoot "scripts\linux\trixie\test_seo_tools_prod.sh"); RemoteDir = "$RemotePath/scripts/linux/trixie/" },
    @{ Local = (Join-Path $projectRoot "scripts\linux\trixie\test_social_tools_prod.sh"); RemoteDir = "$RemotePath/scripts/linux/trixie/" },
    @{ Local = (Join-Path $projectRoot "celery_app.py"); RemoteDir = "$RemotePath/" },
    @{ Local = (Join-Path $projectRoot "tasks\debug_tasks.py"); RemoteDir = "$RemotePath/tasks/" },
    @{ Local = (Join-Path $projectRoot "tasks\__init__.py"); RemoteDir = "$RemotePath/tasks/" }
)

foreach ($f in $filesToCopy) {
    if (-not (Test-Path $f.Local)) {
        Write-Host "❌ Fichier local introuvable: $($f.Local)" -ForegroundColor Red
        exit 1
    }
    scp $f.Local "$User@$Server`:$($f.RemoteDir)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Échec scp: $($f.Local) -> ${Server}:$($f.RemoteDir)" -ForegroundColor Red
        exit 1
    }
}

# Synchroniser aussi sur le master, car une tâche peut être prise par n'importe quel worker
Write-Host "   Synchronisation aussi sur le master ($MasterServer)..." -ForegroundColor Gray
ssh "$MasterUser@$MasterServer" "mkdir -p $MasterRemotePath/tasks" 2>&1 | Out-Null
ssh "$MasterUser@$MasterServer" "mkdir -p $MasterRemotePath/scripts/linux" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de préparer les dossiers sur le master $MasterServer" -ForegroundColor Red
    exit 1
}

$masterFilesToCopy = @(
    @{ Local = (Join-Path $projectRoot "celery_app.py"); RemoteDir = "$MasterRemotePath/" },
    @{ Local = (Join-Path $projectRoot "tasks\debug_tasks.py"); RemoteDir = "$MasterRemotePath/tasks/" },
    @{ Local = (Join-Path $projectRoot "tasks\__init__.py"); RemoteDir = "$MasterRemotePath/tasks/" }
)

foreach ($f in $masterFilesToCopy) {
    if (-not (Test-Path $f.Local)) {
        Write-Host "❌ Fichier local introuvable: $($f.Local)" -ForegroundColor Red
        exit 1
    }
    scp $f.Local "$MasterUser@$MasterServer`:$($f.RemoteDir)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Échec scp: $($f.Local) -> ${MasterServer}:$($f.RemoteDir)" -ForegroundColor Red
        exit 1
    }
}

Write-Host "   Redémarrage des workers Celery (master + worker)..." -ForegroundColor Gray
ssh "$MasterUser@$MasterServer" "sudo systemctl restart prospectlab-celery" 2>&1 | Out-Null
ssh "$User@$Server" "sudo systemctl restart prospectlab-celery" 2>&1 | Out-Null

ssh "$User@$Server" "cd $RemotePath; chmod +x scripts/linux/test_cluster_worker.sh 2>/dev/null || true; bash scripts/linux/test_cluster_worker.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur pendant l'exécution du test sur $Server" -ForegroundColor Red
    Write-Host "   Regarde les messages ci-dessus ou les logs systemd (prospectlab-celery)." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[3/3] Rappel pour vérifier les logs côté Raspberry :" -ForegroundColor Yellow
Write-Host "  ssh $User@$Server 'sudo systemctl status prospectlab-celery'" -ForegroundColor Gray
Write-Host "  ssh $User@$Server 'sudo journalctl -u prospectlab-celery -f'" -ForegroundColor Gray
Write-Host ""
Write-Host "✅ Le script de test du worker s'est terminé sans erreur." -ForegroundColor Green

