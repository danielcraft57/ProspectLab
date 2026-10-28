# Deploiement messagerie Facebook ProspectLab sur serv2 (Debian, aligne SocialDesk messenger).
#
# Usage :
#   .\scripts\facebook_prospection\deploy_to_serv2.ps1

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployScript = Join-Path $Here "_Deploy-FacebookMessengerHost.ps1"

& $DeployScript -SshHost "pi@serv2.lan" -Label "serv2"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Deploy serv2 OK. ProspectLab route messenger_sync / reply / inbox vers pi@serv2.lan (headless)."
Write-Host "Verifier deploy/.env sur serv2 (DATABASE_URL, QDRANT_URL) et service socialdesk-messenger si besoin."
