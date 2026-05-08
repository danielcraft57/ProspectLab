param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'db-server.lan',

    [Parameter(Mandatory=$false)]
    [string]$User = 'deploy',

    [Parameter(Mandatory=$false)]
    [string]$DbName = 'prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$DbUser = 'prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$DbPassword = '',

    [Parameter(Mandatory=$false)]
    [string]$EnvFilePath = '',

    [Parameter(Mandatory=$false)]
    [int]$DbPort = 5432,

    [Parameter(Mandatory=$false)]
    [string]$RemoteBackupDir = '/tmp/prospectlab_backups',

    [Parameter(Mandatory=$false)]
    [string]$LocalOutputDir = '.\backups',

    [Parameter(Mandatory=$false)]
    [switch]$KeepRemoteFile
)

$ErrorActionPreference = 'Stop'

function Get-EnvValueFromFile {
    param(
        [Parameter(Mandatory=$true)]
        [string]$FilePath,

        [Parameter(Mandatory=$true)]
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $FilePath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith('#')) {
            continue
        }
        if ($trimmed -match "^\s*$([regex]::Escape($Key))\s*=\s*(.*)\s*$") {
            $value = $matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                return $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }

    return $null
}

function Get-DbPasswordFromDatabaseUrl {
    param(
        [Parameter(Mandatory=$true)]
        [string]$DatabaseUrl
    )

    try {
        $uri = [Uri]$DatabaseUrl
    } catch {
        return $null
    }

    if ([string]::IsNullOrWhiteSpace($uri.UserInfo)) {
        return $null
    }

    $userInfoParts = $uri.UserInfo.Split(':', 2)
    if ($userInfoParts.Length -lt 2) {
        return $null
    }

    return [System.Uri]::UnescapeDataString($userInfoParts[1])
}

if ([string]::IsNullOrWhiteSpace($DbPassword)) {
    $scriptRoot = Split-Path -Parent $PSScriptRoot
    $projectRoot = Split-Path -Parent $scriptRoot
    $candidateEnvFiles = @()

    if (-not [string]::IsNullOrWhiteSpace($EnvFilePath)) {
        $candidateEnvFiles += $EnvFilePath
    } else {
        $candidateEnvFiles += (Join-Path $projectRoot '.env.prod')
        $candidateEnvFiles += (Join-Path $projectRoot '.env')
    }

    foreach ($envFile in $candidateEnvFiles) {
        $databaseUrl = Get-EnvValueFromFile -FilePath $envFile -Key 'DATABASE_URL'
        if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
            continue
        }

        $dbPasswordFromEnv = Get-DbPasswordFromDatabaseUrl -DatabaseUrl $databaseUrl
        if (-not [string]::IsNullOrWhiteSpace($dbPasswordFromEnv)) {
            $DbPassword = $dbPasswordFromEnv
            Write-Host "Mot de passe DB chargé depuis $envFile (DATABASE_URL)." -ForegroundColor DarkGray
            break
        }
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Backup PostgreSQL distant (ProspectLab)" -ForegroundColor Cyan
Write-Host "Serveur cible : $User@$Server" -ForegroundColor Cyan
Write-Host "Base : $DbName (user=$DbUser, port=$DbPort)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$dbPasswordEscaped = $DbPassword.Replace("'", "'""'""'")

if (-not (Test-Path $LocalOutputDir)) {
    New-Item -ItemType Directory -Path $LocalOutputDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$remoteFile = "$RemoteBackupDir/${DbName}_backup_${timestamp}.sql.gz"
$localFile = Join-Path (Resolve-Path $LocalOutputDir).Path "${DbName}_backup_${timestamp}.sql.gz"
$remoteMinSize = 64

Write-Host "[1/4] Vérification connexion SSH..." -ForegroundColor Yellow
$null = ssh -o ConnectTimeout=8 "$User@$Server" "echo OK" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Connexion SSH impossible vers $User@$Server" -ForegroundColor Red
    exit 1
}
Write-Host "Connexion SSH OK" -ForegroundColor Green
Write-Host ""

Write-Host "[2/4] Génération du dump sur le serveur..." -ForegroundColor Yellow
$remoteScript = @"
set -euo pipefail
mkdir -p '$RemoteBackupDir'
command -v pg_dump >/dev/null 2>&1
command -v gzip >/dev/null 2>&1
if [ -n '$dbPasswordEscaped' ]; then
  export PGPASSWORD='$dbPasswordEscaped'
fi
pg_dump -U '$DbUser' -h 'localhost' -p '$DbPort' -d '$DbName' | gzip > '$remoteFile'
test -s '$remoteFile'
size=`$(stat -c%s '$remoteFile')
if [ "`$size" -lt $remoteMinSize ]; then
  echo 'Dump compresse trop petit (probablement vide)' >&2
  exit 1
fi
echo DUMP_SIZE=`$size
"@
$dumpOutput = $remoteScript | ssh "$User@$Server" "bash -s" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Échec du dump distant (pg_dump/gzip)." -ForegroundColor Red
    Write-Host "Vérifie l'accès PostgreSQL côté serveur (.pgpass/peer/password)." -ForegroundColor Yellow
    if ($dumpOutput) {
        Write-Host $dumpOutput -ForegroundColor DarkYellow
    }
    exit 1
}
Write-Host "Dump distant créé: $remoteFile" -ForegroundColor Green
Write-Host ""

Write-Host "[3/4] Téléchargement du backup..." -ForegroundColor Yellow
$null = scp "$User@$Server`:$remoteFile" "$localFile" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Échec du transfert SCP vers $localFile" -ForegroundColor Red
    exit 1
}

$localSize = (Get-Item $localFile).Length
if ($localSize -lt $remoteMinSize) {
    Write-Host "Backup invalide: fichier trop petit ($localSize octets)." -ForegroundColor Red
    Write-Host "Le dump PostgreSQL semble vide ou incomplet." -ForegroundColor Yellow
    exit 1
}
Write-Host "Backup téléchargé: $localFile" -ForegroundColor Green
Write-Host ""

Write-Host "[4/4] Nettoyage fichier distant..." -ForegroundColor Yellow
if ($KeepRemoteFile) {
    Write-Host "Conservation demandée: le fichier distant n'est pas supprimé." -ForegroundColor Gray
} else {
    $null = ssh "$User@$Server" "rm -f '$remoteFile'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Impossible de supprimer le fichier distant (non bloquant)." -ForegroundColor Yellow
    } else {
        Write-Host "Fichier distant supprimé." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Backup terminé avec succès." -ForegroundColor Green
Write-Host "Fichier local: $localFile" -ForegroundColor Cyan
