# Deploiement du stack Facebook ProspectLab sur un hote Windows (serv1 / serv2).
# Appele par deploy_to_serv.ps1 — ne pas lancer seul sauf debug.

param(
    [Parameter(Mandatory = $true)]
    [string]$SshHost,
    [string]$Label = "hote"
)

$ErrorActionPreference = "Stop"

$FbRemote = "C:/Users/loicDaniel/Documents/SocialDesk/facebook-playwright"
$DeployRemote = "C:/Users/loicDaniel/Documents/SocialDesk/deploy/scripts"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$SocialDesk = "C:\Users\loicDaniel\Documents\SocialDesk"
$WrapperLocal = Join-Path $SocialDesk "deploy\scripts\prospectlab_facebook_remote.py"
$WrapperSrc = Join-Path $Here "run_socialdesk_facebook_remote.py"
$JobMjsLocal = Join-Path $SocialDesk "facebook-playwright\src\prospectlab-facebook-job.mjs"
$TestHostPs1 = Join-Path $Here "test_on_host.ps1"
$InstallHostPs1 = Join-Path $Here "install_facebook_prospectlab_host.ps1"

if (-not (Test-Path $WrapperSrc)) {
    Write-Error "Manquant : $WrapperSrc"
    exit 1
}
if (-not (Test-Path $JobMjsLocal)) {
    Write-Error "Manquant : $JobMjsLocal (clone / sync SocialDesk facebook-playwright sur le poste dev)"
    exit 1
}
if (-not (Test-Path $TestHostPs1)) {
    Write-Error "Manquant : $TestHostPs1"
    exit 1
}

Copy-Item -Path $WrapperSrc -Destination $WrapperLocal -Force

Write-Host "Deploy Facebook -> $Label ($SshHost) ..."

scp "$JobMjsLocal" "${SshHost}:${FbRemote}/src/prospectlab-facebook-job.mjs"
scp "$WrapperLocal" "${SshHost}:${DeployRemote}/prospectlab_facebook_remote.py"
scp "$TestHostPs1" "${SshHost}:${DeployRemote}/test_on_host.ps1"
scp "$TestHostPs1" "${SshHost}:${DeployRemote}/test_on_serv1.ps1"
scp "$TestHostPs1" "${SshHost}:${DeployRemote}/test_on_serv2.ps1"
scp (Join-Path $Here "test_on_host.cmd") "${SshHost}:${DeployRemote}/test_on_host.cmd"
scp (Join-Path $Here "test_on_serv1.cmd") "${SshHost}:${DeployRemote}/test_on_serv1.cmd"
scp (Join-Path $Here "test_on_serv2.cmd") "${SshHost}:${DeployRemote}/test_on_serv2.cmd"

if (Test-Path $InstallHostPs1) {
    scp "$InstallHostPs1" "${SshHost}:${DeployRemote}/install_facebook_prospectlab_host.ps1"
}

Write-Host "OK $Label. RDP puis :"
Write-Host "  cd $DeployRemote"
Write-Host "  .\install_facebook_prospectlab_host.ps1"
Write-Host '  .\test_on_host.ps1 search "boulangerie metz"'
