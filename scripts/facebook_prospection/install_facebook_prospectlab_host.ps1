# Verification prep hote Windows serv1 pour jobs SSH ProspectLab.
# A lancer en RDP une fois apres deploy_to_serv.ps1

$ErrorActionPreference = "Continue"

$FbRoot = "C:\Users\loicDaniel\Documents\SocialDesk\facebook-playwright"
$Deploy = "C:\Users\loicDaniel\Documents\SocialDesk\deploy\scripts"
$Wrapper = Join-Path $Deploy "prospectlab_facebook_remote.py"
$JobMjs = Join-Path $FbRoot "src\prospectlab-facebook-job.mjs"
$HostName = $env:COMPUTERNAME

Write-Host "=== ProspectLab Facebook host : $HostName ==="

$script:HostOk = $true

function Test-PathOk {
    param([string]$Path, [string]$Msg)
    if (Test-Path $Path) {
        Write-Host "[OK] $Msg"
        return $true
    }
    Write-Host "[KO] $Msg — manquant : $Path"
    $script:HostOk = $false
    return $false
}

Test-PathOk $JobMjs "prospectlab-facebook-job.mjs"
Test-PathOk $Wrapper "prospectlab_facebook_remote.py (wrapper SSH)"

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "[OK] Node.js : $($node.Source)"
    node --version
} else {
    Write-Host "[KO] Node.js absent du PATH"
    $script:HostOk = $false
}

$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    Write-Host "[OK] Python : $($py.Source)"
    python --version
} else {
    Write-Host "[WARN] Python absent (wrapper utilise python -u sur SSH)"
}

if ($HostName -match 'serv2') {
    Write-Host ""
    Write-Host "ATTENTION : serv2 est Debian — ce script est pour serv1 Windows uniquement."
    $script:HostOk = $false
} else {
    Write-Host ""
    Write-Host "serv1 : recherche / scrape / Messenger (Windows + SocialDesk)."
    Write-Host "Verifier SocialDesk schedule (cookies 5h)."
}

Write-Host ""
Write-Host "Test rapide (Chrome visible si headless=false) :"
Write-Host "  cd $Deploy"
Write-Host '  .\test_on_host.ps1 search "test prospectlab"'

if (-not $script:HostOk) {
    Write-Host ""
    Write-Host "Corrigez les [KO] puis relancez ce script."
    exit 1
}

Write-Host ""
Write-Host "Hote pret pour SSH depuis node15 (meme cle que audit PDF)."
