# Envoie uniquement templates/ et static/ vers le serveur (sans refaire tout le déploiement)
# Usage: .\scripts\sync_templates_static.ps1 [serveur] [utilisateur]
# Exemple: .\scripts\sync_templates_static.ps1 node15.lan pi

param(
    [Parameter(Mandatory=$false)]
    [string]$Server = 'node15.lan',
    [Parameter(Mandatory=$false)]
    [string]$User = 'pi',
    [Parameter(Mandatory=$false)]
    [string]$RemotePath = '/opt/prospectlab'
)

$ErrorActionPreference = 'Stop'
$PROJECT_DIR = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName

$templatesPath = Join-Path $PROJECT_DIR "templates"
$staticPath = Join-Path $PROJECT_DIR "static"

if (-not (Test-Path $templatesPath)) {
    Write-Host "Erreur: templates introuvable dans $templatesPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $staticPath)) {
    Write-Host "Erreur: static introuvable dans $staticPath" -ForegroundColor Red
    exit 1
}

Write-Host "Envoi de templates et static vers $User@$Server`:$RemotePath" -ForegroundColor Cyan
scp -r "$templatesPath" "$User@$Server`:$RemotePath/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erreur lors de l'envoi de templates" -ForegroundColor Red
    exit 1
}
scp -r "$staticPath" "$User@$Server`:$RemotePath/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erreur lors de l'envoi de static" -ForegroundColor Red
    exit 1
}
Write-Host "OK. templates et static sont a jour sur le serveur." -ForegroundColor Green
