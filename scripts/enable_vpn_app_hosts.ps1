<#
.SYNOPSIS
    Force prospectlab/campaigns vers l'IP LAN Nginx (evite le contournement VPN Windows).

.PARAMETER Remove
    Retire les entrees hosts + regles NRPT.
#>
[CmdletBinding()]
param(
    [string]$LanIp = '192.168.1.209',
    [string]$VpnDns = '192.168.1.191',
    [string[]]$Hostnames = @('prospectlab.danielcraft.fr', 'campaigns.danielcraft.fr'),
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$hostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$marker = '# prospectlab-vpn-access'

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "Relance en admin..." -ForegroundColor Yellow
    $argList = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $PSCommandPath)
    )
    if ($Remove) { $argList += '-Remove' }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList -Wait
    exit $LASTEXITCODE
}

$raw = Get-Content -LiteralPath $hostsPath -ErrorAction Stop
$filtered = @(
    $raw | Where-Object {
        $_ -notmatch [regex]::Escape($marker) -and
        ($_ -notmatch 'prospectlab\.danielcraft\.fr') -and
        ($_ -notmatch 'campaigns\.danielcraft\.fr')
    }
)

Get-DnsClientNrptRule -ErrorAction SilentlyContinue |
    Where-Object { $_.Namespace -match 'danielcraft\.fr' } |
    ForEach-Object { Remove-DnsClientNrptRule -Name $_.Name -Force -ErrorAction SilentlyContinue }

if ($Remove) {
    Set-Content -LiteralPath $hostsPath -Value $filtered -Encoding ASCII
    Write-Host "Hosts/NRPT ProspectLab retires." -ForegroundColor Green
    ipconfig /flushdns | Out-Null
    exit 0
}

$lines = New-Object System.Collections.Generic.List[string]
foreach ($h in $Hostnames) {
    $lines.Add("$LanIp`t$h`t$marker")
    Add-DnsClientNrptRule -Namespace $h -NameServers $VpnDns -ErrorAction SilentlyContinue | Out-Null
}
$newContent = $filtered + $lines.ToArray()
Set-Content -LiteralPath $hostsPath -Value $newContent -Encoding ASCII
ipconfig /flushdns | Out-Null

Write-Host "OK: domaines ProspectLab -> $LanIp (hosts + NRPT DNS $VpnDns)" -ForegroundColor Green
Write-Host "Recharge https://prospectlab.danielcraft.fr/" -ForegroundColor Gray
