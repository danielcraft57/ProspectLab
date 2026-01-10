# Script de test des outils OSINT et Pentest dans WSL

Write-Host "Test des outils OSINT et Pentest dans WSL kali-linux..." -ForegroundColor Green
Write-Host ""

$wslDistro = "kali-linux"
$wslUser = "loupix"

# Outils OSINT
$osintTools = @(
    'dnsrecon',
    'theharvester',
    'sublist3r',
    'amass',
    'whatweb',
    'sslscan',
    'sherlock',
    'maigret'
)

# Outils Pentest
$pentestTools = @(
    'sqlmap',
    'wpscan',
    'nikto',
    'wapiti',
    'nmap',
    'sslscan'
)

function Test-Tool {
    param(
        [string]$toolName,
        [string]$distro,
        [string]$user
    )
    
    Write-Host "  Test de $toolName..." -NoNewline
    
    # Essayer avec l'utilisateur
    try {
        $result = wsl -d $distro -u $user which $toolName 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK (avec utilisateur)" -ForegroundColor Green
            return $true
        }
    } catch {
        # Ignorer l'erreur
    }
    
    # Essayer sans utilisateur
    try {
        $result = wsl -d $distro which $toolName 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK (sans utilisateur)" -ForegroundColor Green
            return $true
        }
    } catch {
        # Ignorer l'erreur
    }
    
    # Essayer avec --version pour certains outils
    try {
        $result = wsl -d $distro $toolName --version 2>&1
        if ($LASTEXITCODE -eq 0 -or $result -match "version|Version") {
            Write-Host " OK (test version)" -ForegroundColor Green
            return $true
        }
    } catch {
        # Ignorer l'erreur
    }
    
    Write-Host " NON DISPONIBLE" -ForegroundColor Red
    return $false
}

Write-Host "=== Outils OSINT ===" -ForegroundColor Cyan
$osintAvailable = 0
foreach ($tool in $osintTools) {
    if (Test-Tool -toolName $tool -distro $wslDistro -user $wslUser) {
        $osintAvailable++
    }
}

Write-Host ""
Write-Host "=== Outils Pentest ===" -ForegroundColor Cyan
$pentestAvailable = 0
foreach ($tool in $pentestTools) {
    if (Test-Tool -toolName $tool -distro $wslDistro -user $wslUser) {
        $pentestAvailable++
    }
}

Write-Host ""
Write-Host "=== Résumé ===" -ForegroundColor Yellow
Write-Host "Outils OSINT disponibles: $osintAvailable / $($osintTools.Count)" -ForegroundColor $(if ($osintAvailable -gt 0) { "Green" } else { "Red" })
Write-Host "Outils Pentest disponibles: $pentestAvailable / $($pentestTools.Count)" -ForegroundColor $(if ($pentestAvailable -gt 0) { "Green" } else { "Red" })

