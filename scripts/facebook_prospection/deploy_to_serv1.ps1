# Copie les bina/scripts Facebook ProspectLab vers serv1 (poste dev).
# Usage : .\deploy_to_serv1.ps1  (equivalent deploy_to_serv.ps1 -Target serv1)

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Here "deploy_to_serv.ps1") -Target serv1
