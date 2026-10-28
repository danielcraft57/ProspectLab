# Deploiement wrapper ProspectLab + prospectlab-facebook-job.mjs sur serv2 (Debian / SocialDesk messenger).

param(
    [string]$SshHost = "pi@serv2.lan",
    [string]$Label = "serv2"
)

$ErrorActionPreference = "Stop"

$FbRemote = "/home/pi/Documents/socialdesk/facebook-playwright"
$DeployRemote = "/home/pi/Documents/socialdesk/deploy/scripts"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$SocialDesk = "C:\Users\loicDaniel\Documents\SocialDesk"
$WrapperSrc = Join-Path $Here "run_socialdesk_facebook_remote.py"
$JobMjsLocal = Join-Path $SocialDesk "facebook-playwright\src\prospectlab-facebook-job.mjs"
$TestSh = Join-Path $Here "test_on_serv2.sh"
$InstallSh = Join-Path $Here "install_facebook_messenger_serv2.sh"

if (-not (Test-Path $WrapperSrc)) {
    Write-Error "Manquant : $WrapperSrc"
    exit 1
}
if (-not (Test-Path $JobMjsLocal)) {
    Write-Error "Manquant : $JobMjsLocal"
    exit 1
}

Write-Host "Deploy Facebook Messenger -> $Label ($SshHost) ..."

ssh $SshHost "mkdir -p $FbRemote/src $DeployRemote"

scp "$JobMjsLocal" "${SshHost}:${FbRemote}/src/prospectlab-facebook-job.mjs"
scp "$WrapperSrc" "${SshHost}:${DeployRemote}/prospectlab_facebook_remote.py"

if (Test-Path $TestSh) {
    scp "$TestSh" "${SshHost}:${DeployRemote}/test_on_serv2.sh"
}
if (Test-Path $InstallSh) {
    scp "$InstallSh" "${SshHost}:${DeployRemote}/install_facebook_messenger_serv2.sh"
}

Write-Host "OK $Label. Puis SSH :"
Write-Host "  cd $DeployRemote"
Write-Host "  chmod +x test_on_serv2.sh install_facebook_messenger_serv2.sh"
Write-Host "  ./install_facebook_messenger_serv2.sh"
Write-Host "  ./test_on_serv2.sh sync"
