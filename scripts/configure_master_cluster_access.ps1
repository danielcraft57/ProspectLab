param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'master.lan',

    [Parameter(Mandatory=$false)]
    [string]$User = 'deploy',

    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab'
)

$ErrorActionPreference = 'Stop'

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Configuration du master ProspectLab pour le cluster" -ForegroundColor Cyan
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

Write-Host "[2/3] Lancement de configure_master_cluster_access.sh sur le serveur..." -ForegroundColor Yellow

$remoteScript = "$RemotePath/scripts/linux/configure_master_cluster_access.sh"

# Toujours pousser le script master via scp (évite d'exécuter une ancienne version)
ssh "$User@$Server" "mkdir -p $RemotePath/scripts/linux" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de créer $RemotePath/scripts/linux sur $Server (vérifie les permissions)" -ForegroundColor Red
    exit 1
}

Write-Host "   Synchronisation du script master via scp..." -ForegroundColor Gray
$localScript = Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\linux\configure_master_cluster_access.sh"
if (-not (Test-Path $localScript)) {
    Write-Host "❌ Script local introuvable: $localScript" -ForegroundColor Red
    exit 1
}
scp $localScript "$User@$Server`:$RemotePath/scripts/linux/" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Impossible de copier configure_master_cluster_access.sh sur $Server" -ForegroundColor Red
    exit 1
}

ssh "$User@$Server" "cd $RemotePath; chmod +x scripts/linux/configure_master_cluster_access.sh 2>/dev/null || true; bash scripts/linux/configure_master_cluster_access.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur pendant la configuration du master sur $Server" -ForegroundColor Red
    Write-Host "   Regarde les messages ci-dessus et les logs redis/postgresql." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[3/3] Rappels rapides :" -ForegroundColor Yellow
Write-Host "  - Sur $Server, vérifier Redis :" -ForegroundColor Gray
Write-Host "      sudo systemctl status redis-server" -ForegroundColor Gray
Write-Host "  - Sur $Server, vérifier PostgreSQL :" -ForegroundColor Gray
Write-Host "      sudo systemctl status postgresql" -ForegroundColor Gray
Write-Host ""
Write-Host "  - Depuis un worker, tester Redis :" -ForegroundColor Gray
Write-Host "      redis-cli -h <master-host> -p 6379 ping" -ForegroundColor Gray
Write-Host ""
Write-Host "✅ Configuration du master pour le cluster terminée." -ForegroundColor Green

