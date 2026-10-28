# Tests directs sur serv1 ou serv2 (RDP). Pas d'enregistrement BDD ProspectLab.
#
# Usage :
#   .\test_on_host.ps1 search "boulangerie metz"
#   .\test_on_host.ps1 prospect -Query "Hotel des Ventes de Metz" -AddressHint "43 Rue Dupont des Loges, 57000 Metz"

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('search', 'prospect')]
    [string]$JobType,
    [Parameter(Position = 1)]
    [string]$Query = "",
    [string]$TargetName = "",
    [string]$AddressHint = "",
    [string]$MessageText = "Bonjour, test ProspectLab prospect_flow (dry-run).",
    [switch]$Send,
    [string]$FbRoot = "C:\Users\loicDaniel\Documents\SocialDesk\facebook-playwright",
    [string]$Account = "danielcraft",
    [bool]$Headless = $false
)

if ($JobType -eq 'search' -and -not $Query.Trim()) {
    Write-Error 'Usage: .\test_on_host.ps1 search "boulangerie metz"'
    exit 1
}
if ($JobType -eq 'prospect' -and -not $Query.Trim()) {
    Write-Error 'Usage: .\test_on_host.ps1 prospect -Query "Nom entreprise" [-AddressHint "..."]'
    exit 1
}

$script = Join-Path $FbRoot "src\prospectlab-facebook-job.mjs"
if (-not (Test-Path $script)) {
    Write-Error "Manquant : $script (lance deploy_to_serv.ps1 depuis le poste dev)"
    exit 1
}

if ($JobType -eq 'search') {
    $job = @{
        job_type = "search"
        account  = $Account
        payload  = @{
            query         = $Query.Trim()
            target_name   = if ($TargetName) { $TargetName } else { $Query.Trim() }
            address_hint  = $AddressHint
            headless      = $Headless
        }
    }
    Write-Host "search headless=$Headless sur $env:COMPUTERNAME ..."
} else {
    $job = @{
        job_type = "prospect_flow"
        account  = $Account
        payload  = @{
            query         = $Query.Trim()
            target_name   = if ($TargetName) { $TargetName } else { $Query.Trim() }
            address_hint  = $AddressHint
            message_text  = $MessageText
            send          = [bool]$Send
            headless      = $Headless
        }
    }
    Write-Host "prospect_flow send=$Send headless=$Headless sur $env:COMPUTERNAME ..."
}

$json = $job | ConvertTo-Json -Compress -Depth 6
Set-Location $FbRoot
$json | node $script
exit $LASTEXITCODE
