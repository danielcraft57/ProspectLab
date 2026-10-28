# Deploiement du stack Facebook ProspectLab sur serv1 (Windows + Chrome).
# Messagerie inbox : deploy_to_serv2.ps1 (Debian).
#
# Usage :
#   .\deploy_to_serv.ps1
#   .\deploy_to_serv1.ps1

param(
    [ValidateSet("serv1")]
    [string]$Target = "serv1"
)

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployScript = Join-Path $Here "_Deploy-FacebookHost.ps1"

& $DeployScript -SshHost "loicDaniel@serv1.lan" -Label "serv1"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Deploy serv1 OK. Affectation auto ProspectLab : serv1 (file Celery)."
Write-Host "Pour un 2e poste Windows : FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT dans .env + deploy identique sur cet hote."
