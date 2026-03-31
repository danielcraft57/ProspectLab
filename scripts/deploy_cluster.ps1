param(
    [Parameter(Mandatory=$false)]
    [string[]]$Nodes = @('worker1.lan','worker2.lan'),

    [Parameter(Mandatory=$false)]
    [string]$User = 'deploy',

    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$EnvFile = '.env.cluster',

    [Parameter(Mandatory=$false)]
    [switch]$SkipInstall,

    [Parameter(Mandatory=$false)]
    [switch]$CopyOnly,

    [Parameter(Mandatory=$false)]
    [switch]$SkipRestart,

    [Parameter(Mandatory=$false)]
    [switch]$SkipNfsClient
)

$ErrorActionPreference = 'Stop'

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)] [string] $FilePath,
        [Parameter(Mandatory = $true)] [string] $Key
    )
    if (-not (Test-Path -LiteralPath $FilePath)) { return '' }
    $prefix = $Key + '='
    foreach ($raw in Get-Content -LiteralPath $FilePath) {
        $line = $raw.Trim()
        if ($line.StartsWith('#')) { continue }
        if ($line -eq '') { continue }
        if ($line.StartsWith($prefix)) {
            return $line.Substring($prefix.Length).Trim()
        }
    }
    return ''
}

$projectDir = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$installScript = Join-Path $PSScriptRoot 'install_cluster_worker.ps1'
$envFilePath = Join-Path $projectDir $EnvFile

# Tolérer un passage CSV unique:
# -Nodes "node10.lan,node11.lan"
if ($Nodes.Count -eq 1 -and $Nodes[0] -like '*,*') {
    $Nodes = $Nodes[0].Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Déploiement multi-noeuds du cluster ProspectLab" -ForegroundColor Cyan
Write-Host "Noeuds : $($Nodes -join ', ')" -ForegroundColor Cyan
Write-Host "User   : $User" -ForegroundColor Cyan
Write-Host "Remote : $RemotePath" -ForegroundColor Cyan
Write-Host "Env    : $EnvFile" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $installScript)) {
    Write-Host "Script introuvable: $installScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $envFilePath)) {
    Write-Host "Fichier d'environnement introuvable: $envFilePath" -ForegroundColor Red
    Write-Host "Copie d'abord env.cluster.example vers .env.cluster puis adapte les valeurs." -ForegroundColor Yellow
    exit 1
}

if ($Nodes.Count -eq 0) {
    Write-Host "Aucun noeud fourni. Utilise -Nodes worker1.lan,worker2.lan par exemple." -ForegroundColor Red
    exit 1
}

$results = @()

foreach ($node in $Nodes) {
    Write-Host ""
    Write-Host "------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "Noeud: $node" -ForegroundColor Cyan
    Write-Host "------------------------------------------" -ForegroundColor DarkCyan

    $nodeOk = $true
    $nodeErrors = @()

    try {
        Write-Host "[1/5] Vérification SSH..." -ForegroundColor Yellow
        $null = ssh -o ConnectTimeout=8 "$User@$node" "echo OK" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Connexion SSH impossible vers $User@$node"
        }
        Write-Host "Connexion SSH OK" -ForegroundColor Green
    } catch {
        $nodeOk = $false
        $nodeErrors += $_.Exception.Message
    }

    if ($nodeOk -and $CopyOnly) {
        try {
            Write-Host "[2/5] Copie code uniquement (-CopyOnly) ..." -ForegroundColor Yellow
            & $installScript -Server $node -User $User -RemotePath $RemotePath -SkipRemoteInstallScript
            if ($LASTEXITCODE -ne 0) {
                throw "install_cluster_worker.ps1 a échoué en mode copie-only pour $node"
            }
            Write-Host "Copie code OK (pas d'installation distante)" -ForegroundColor Green
        } catch {
            $nodeOk = $false
            $nodeErrors += $_.Exception.Message
        }
    } elseif ($nodeOk -and -not $SkipInstall) {
        try {
            Write-Host "[2/5] Installation/synchronisation worker..." -ForegroundColor Yellow
            & $installScript -Server $node -User $User -RemotePath $RemotePath
            if ($LASTEXITCODE -ne 0) {
                throw "install_cluster_worker.ps1 a échoué pour $node"
            }
            Write-Host "Installation/synchronisation OK" -ForegroundColor Green
        } catch {
            $nodeOk = $false
            $nodeErrors += $_.Exception.Message
        }
    } elseif ($nodeOk) {
        Write-Host "[2/5] Install ignorée (-SkipInstall)." -ForegroundColor DarkYellow
    }

    if ($nodeOk -and -not $SkipNfsClient) {
        try {
            $nfsSkipMountRaw = Get-DotEnvValue -FilePath $envFilePath -Key 'NFS_SKIP_CLIENT_MOUNT'
            $nfsSkipNode = $false
            if (-not [string]::IsNullOrWhiteSpace($nfsSkipMountRaw)) {
                $tskip = $nfsSkipMountRaw.Trim().ToLowerInvariant()
                $nfsSkipNode = @('1', 'true', 'yes', 'on') -contains $tskip
            }
            $nfsServerNode = Get-DotEnvValue -FilePath $envFilePath -Key 'NFS_SERVER'
            $nfsExportNode = Get-DotEnvValue -FilePath $envFilePath -Key 'NFS_EXPORT_ROOT'
            if ([string]::IsNullOrWhiteSpace($nfsExportNode)) {
                $nfsExportNode = '/srv/nfs/prospectlab'
            }
            if ($nfsSkipNode) {
                Write-Host "[2b/5] Montage NFS ignoré sur $node (NFS_SKIP_CLIENT_MOUNT)." -ForegroundColor DarkYellow
            }
            if (-not $nfsSkipNode -and -not [string]::IsNullOrWhiteSpace($nfsServerNode)) {
                $nfsAutoStashRaw = Get-DotEnvValue -FilePath $envFilePath -Key 'NFS_AUTO_STASH'
                if ([string]::IsNullOrWhiteSpace($nfsAutoStashRaw)) {
                    $nfsAutoStashVal = '1'
                } else {
                    $nfsAutoStashNorm = $nfsAutoStashRaw.Trim().ToLowerInvariant()
                    if (@('0', 'false', 'no', 'off') -contains $nfsAutoStashNorm) {
                        $nfsAutoStashVal = '0'
                    } else {
                        $nfsAutoStashVal = '1'
                    }
                }
                Write-Host "[2b/5] Montage NFS client ($nfsServerNode, NFS_AUTO_STASH=$nfsAutoStashVal)..." -ForegroundColor Yellow
                $nfsRemoteScript = "$RemotePath/scripts/linux/setup_nfs_client_prospectlab.sh"
                $nfsLocalScript = Join-Path $projectDir 'scripts\linux\setup_nfs_client_prospectlab.sh'
                if (-not (Test-Path -LiteralPath $nfsLocalScript)) {
                    throw "Script local introuvable : $nfsLocalScript"
                }
                $null = ssh "$User@$node" "mkdir -p $RemotePath/scripts/linux" 2>&1
                if ($LASTEXITCODE -ne 0) {
                    throw "Impossible de créer $RemotePath/scripts/linux sur $node"
                }
                $null = ssh "$User@$node" "test -f $nfsRemoteScript" 2>&1
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "   Copie du script NFS depuis le poste local (-SkipInstall)..." -ForegroundColor Gray
                    scp $nfsLocalScript "${User}@${node}:${RemotePath}/scripts/linux/setup_nfs_client_prospectlab.sh" 2>&1 | Out-Null
                    if ($LASTEXITCODE -ne 0) {
                        throw "SCP du script NFS vers $node a échoué"
                    }
                    $null = ssh "$User@$node" "chmod +x $nfsRemoteScript" 2>&1
                }
                $null = ssh "$User@$node" "sudo env REMOTE_PATH=$RemotePath NFS_SERVER=$nfsServerNode NFS_EXPORT_ROOT=$nfsExportNode NFS_AUTO_STASH=$nfsAutoStashVal bash $nfsRemoteScript" 2>&1
                if ($LASTEXITCODE -ne 0) {
                    throw "Montage NFS échoué sur $node"
                }
                Write-Host "Montage NFS OK" -ForegroundColor Green
            }
        } catch {
            $nodeOk = $false
            $nodeErrors += $_.Exception.Message
        }
    }

    if ($nodeOk) {
        try {
            Write-Host "[3/5] Copie de $EnvFile vers $RemotePath/.env..." -ForegroundColor Yellow
            $null = scp "$envFilePath" "$User@$node`:$RemotePath/.env" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Copie .env échouée vers $node"
            }
            Write-Host "Copie .env OK" -ForegroundColor Green
        } catch {
            $nodeOk = $false
            $nodeErrors += $_.Exception.Message
        }
    }

    if ($nodeOk -and -not $SkipRestart) {
        try {
            Write-Host "[4/5] Nettoyage des logs applicatifs (scripts/linux/clear-logs.sh)..." -ForegroundColor Yellow
            $null = ssh "$User@$node" "cd $RemotePath && bash scripts/linux/clear-logs.sh" 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Avertissement : clear-logs a échoué sur $node (non bloquant)." -ForegroundColor DarkYellow
            } else {
                Write-Host "Logs nettoyés dans $RemotePath/logs" -ForegroundColor Green
            }

            Write-Host "[5/5] Redémarrage service Celery..." -ForegroundColor Yellow
            $null = ssh "$User@$node" "sudo systemctl enable prospectlab-celery" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Impossible d'activer le service prospectlab-celery sur $node"
            }

            $null = ssh "$User@$node" "sudo systemctl restart prospectlab-celery" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Impossible de redémarrer prospectlab-celery sur $node"
            }

            $null = ssh "$User@$node" "sudo systemctl is-active prospectlab-celery" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Le service prospectlab-celery n'est pas actif sur $node"
            }

            Write-Host "Service Celery actif" -ForegroundColor Green
        } catch {
            $nodeOk = $false
            $nodeErrors += $_.Exception.Message
        }
    } elseif ($nodeOk) {
        Write-Host "[4/5]-[5/5] Clear logs + restart ignorés (-SkipRestart)." -ForegroundColor DarkYellow
    }

    if ($nodeOk) {
        $results += [PSCustomObject]@{
            Node = $node
            Status = 'OK'
            Details = 'Deploy + .env + service OK'
        }
        Write-Host "Noeud $node terminé avec succès." -ForegroundColor Green
    } else {
        $results += [PSCustomObject]@{
            Node = $node
            Status = 'KO'
            Details = ($nodeErrors -join ' | ')
        }
        Write-Host "Noeud $node en échec." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Résumé déploiement cluster" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
$results | Format-Table -AutoSize

$failed = $results | Where-Object { $_.Status -eq 'KO' }
if ($failed.Count -gt 0) {
    exit 1
}

Write-Host "Déploiement terminé sur tous les noeuds." -ForegroundColor Green
