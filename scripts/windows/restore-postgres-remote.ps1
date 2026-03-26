param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'node15.lan',

    [Parameter(Mandatory=$false)]
    [string]$User = 'pi',

    [Parameter(Mandatory=$true)]
    [string]$BackupFile,

    [Parameter(Mandatory=$false)]
    [string]$DbName = 'prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$DbUser = 'prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$DbPassword = '',

    [Parameter(Mandatory=$false)]
    [int]$DbPort = 5432,

    [Parameter(Mandatory=$false)]
    [string]$RemoteTempDir = '/tmp/prospectlab_restore',

    [Parameter(Mandatory=$false)]
    [switch]$RecreateDatabase
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $BackupFile)) {
    Write-Host "Fichier backup introuvable: $BackupFile" -ForegroundColor Red
    exit 1
}

$backupFullPath = (Resolve-Path $BackupFile).Path
$fileName = [System.IO.Path]::GetFileName($backupFullPath)
$remoteFile = "$RemoteTempDir/$fileName"
$isGzip = $fileName.ToLower().EndsWith(".gz")
$dbPasswordEscaped = $DbPassword.Replace("'", "'""'""'")

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Restore PostgreSQL distant (ProspectLab)" -ForegroundColor Cyan
Write-Host "Serveur cible : $User@$Server" -ForegroundColor Cyan
Write-Host "Base cible : $DbName (user=$DbUser, port=$DbPort)" -ForegroundColor Cyan
Write-Host "Backup local : $backupFullPath" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Vérification connexion SSH..." -ForegroundColor Yellow
$null = ssh -o ConnectTimeout=8 "$User@$Server" "echo OK" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Connexion SSH impossible vers $User@$Server" -ForegroundColor Red
    exit 1
}
Write-Host "Connexion SSH OK" -ForegroundColor Green
Write-Host ""

Write-Host "[2/4] Envoi du backup sur le serveur..." -ForegroundColor Yellow
$null = ssh "$User@$Server" "mkdir -p '$RemoteTempDir'" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Impossible de créer $RemoteTempDir sur le serveur." -ForegroundColor Red
    exit 1
}

$null = scp "$backupFullPath" "$User@$Server`:$remoteFile" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Échec du transfert SCP vers $remoteFile" -ForegroundColor Red
    exit 1
}
Write-Host "Backup transféré: $remoteFile" -ForegroundColor Green
Write-Host ""

Write-Host "[3/4] Restauration de la base..." -ForegroundColor Yellow

if ($RecreateDatabase) {
    Write-Host "Mode recreate activé: suppression/recréation de la base avant import." -ForegroundColor Yellow
    $dropCreateCmd = "bash -lc ""set -euo pipefail; if [ -n '$dbPasswordEscaped' ]; then export PGPASSWORD='$dbPasswordEscaped'; fi; psql -v ON_ERROR_STOP=1 -U '$DbUser' -h 'localhost' -p '$DbPort' -d postgres -c \""SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DbName' AND pid <> pg_backend_pid();\"" -c \""DROP DATABASE IF EXISTS $DbName;\"" -c \""CREATE DATABASE $DbName;\"""""
    $null = ssh "$User@$Server" $dropCreateCmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Échec DROP/CREATE de la base $DbName." -ForegroundColor Red
        exit 1
    }
}

if ($isGzip) {
    $restoreCmd = "bash -lc ""set -euo pipefail; if [ -n '$dbPasswordEscaped' ]; then export PGPASSWORD='$dbPasswordEscaped'; fi; gunzip -c '$remoteFile' | psql -v ON_ERROR_STOP=1 -U '$DbUser' -h 'localhost' -p '$DbPort' -d '$DbName'"""
} else {
    $restoreCmd = "bash -lc ""set -euo pipefail; if [ -n '$dbPasswordEscaped' ]; then export PGPASSWORD='$dbPasswordEscaped'; fi; psql -v ON_ERROR_STOP=1 -U '$DbUser' -h 'localhost' -p '$DbPort' -d '$DbName' -f '$remoteFile'"""
}

$null = ssh "$User@$Server" $restoreCmd 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Échec de la restauration PostgreSQL." -ForegroundColor Red
    Write-Host "Vérifie les droits DB et le format du dump." -ForegroundColor Yellow
    exit 1
}
Write-Host "Restauration terminée avec succès." -ForegroundColor Green
Write-Host ""

Write-Host "[4/4] Nettoyage du fichier temporaire distant..." -ForegroundColor Yellow
$null = ssh "$User@$Server" "rm -f '$remoteFile'" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Impossible de supprimer le fichier temporaire distant (non bloquant)." -ForegroundColor Yellow
} else {
    Write-Host "Fichier temporaire supprimé." -ForegroundColor Green
}

Write-Host ""
Write-Host "Restore terminé." -ForegroundColor Green
