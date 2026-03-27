param(
    [Parameter(Mandatory=$false)]
    [string[]]$Nodes = @('node10.lan','node11.lan','node12.lan','node13.lan', 'node14.lan'),

    [Parameter(Mandatory=$false)]
    [string]$User = 'pi',

    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab',

    [Parameter(Mandatory=$false)]
    [string]$EnvFile = '.env.cluster',

    [Parameter(Mandatory=$false)]
    [switch]$SkipInstall,

    [Parameter(Mandatory=$false)]
    [switch]$SkipRestart
)

$ErrorActionPreference = 'Stop'

$projectDir = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$installScript = Join-Path $PSScriptRoot 'install_cluster_worker.ps1'
$envFilePath = Join-Path $projectDir $EnvFile

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
    Write-Host "Aucun noeud fourni. Utilise -Nodes node13.lan,node14.lan par exemple." -ForegroundColor Red
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
        Write-Host "[1/4] Vérification SSH..." -ForegroundColor Yellow
        $null = ssh -o ConnectTimeout=8 "$User@$node" "echo OK" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Connexion SSH impossible vers $User@$node"
        }
        Write-Host "Connexion SSH OK" -ForegroundColor Green
    } catch {
        $nodeOk = $false
        $nodeErrors += $_.Exception.Message
    }

    if ($nodeOk -and -not $SkipInstall) {
        try {
            Write-Host "[2/4] Installation/synchronisation worker..." -ForegroundColor Yellow
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
        Write-Host "[2/4] Install ignorée (-SkipInstall)." -ForegroundColor DarkYellow
    }

    if ($nodeOk) {
        try {
            Write-Host "[3/4] Copie de $EnvFile vers $RemotePath/.env..." -ForegroundColor Yellow
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
            Write-Host "[4/4] Redémarrage service Celery..." -ForegroundColor Yellow
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
        Write-Host "[4/4] Restart ignoré (-SkipRestart)." -ForegroundColor DarkYellow
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
