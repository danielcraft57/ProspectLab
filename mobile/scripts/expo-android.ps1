#Requires -Version 5.1
<#
.SYNOPSIS
  Prépare ADB (optionnellement en Wi-Fi) puis lance npx expo run:android.
.PARAMETER Wireless
  Adresse du téléphone en ADB TCP, ex. 192.168.1.190:5555. Si vide, utilise les appareils déjà listés par adb.
.PARAMETER SkipConnect
  Ne fait pas kill-server / connect (ADB déjà prêt).
#>
param(
  [string] $Wireless = "",
  [switch] $SkipConnect,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $ExpoArgs
)

$ErrorActionPreference = "Stop"

$AndroidHome = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$script:AdbExe = Join-Path $AndroidHome "platform-tools\adb.exe"
if (-not (Test-Path $script:AdbExe)) {
  Write-Error "adb introuvable: $script:AdbExe (installe Android SDK Platform-Tools)."
}

function Invoke-AdbQuiet {
  param([string[]] $AdbArguments)
  $old = $ErrorActionPreference
  $ErrorActionPreference = "SilentlyContinue"
  $null = & $script:AdbExe @AdbArguments 2>&1
  $ErrorActionPreference = $old
}

# Répertoire mobile/ (parent de scripts/)
$mobileRoot = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $mobileRoot "package.json"))) {
  Write-Error "package.json introuvable dans $mobileRoot"
}

Set-Location $mobileRoot
$env:ANDROID_HOME = $AndroidHome
$env:Path = "$(Join-Path $AndroidHome 'platform-tools');$(Join-Path $AndroidHome 'emulator');$env:Path"

function Get-JdkMajorFromRelease {
  param([string] $JavaHome)
  $rf = Join-Path $JavaHome "release"
  if (-not (Test-Path $rf)) { return $null }
  $raw = Get-Content $rf -Raw -ErrorAction SilentlyContinue
  if ($raw -match 'JAVA_VERSION="?(\d+)') { return [int]$Matches[1] }
  return $null
}

function Find-Jdk21 {
  $roots = @(
    (Join-Path $env:ProgramFiles "Java"),
    (Join-Path $env:ProgramFiles "Eclipse Adoptium"),
    (Join-Path $env:ProgramFiles "Microsoft"),
    (Join-Path $env:ProgramFiles "Amazon Corretto"),
    (Join-Path $env:ProgramFiles "Zulu"),
    (Join-Path $env:LOCALAPPDATA "Programs\Eclipse Adoptium")
  )
  foreach ($root in $roots) {
    if (-not (Test-Path $root)) { continue }
    foreach ($d in Get-ChildItem $root -Directory -ErrorAction SilentlyContinue) {
      $maj = Get-JdkMajorFromRelease $d.FullName
      if ($maj -eq 21 -and (Test-Path (Join-Path $d.FullName "bin\java.exe"))) {
        return $d.FullName
      }
    }
  }
  return $null
}

function Resolve-JavaHome {
  $j21 = Find-Jdk21
  if ($j21) { return $j21 }
  if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
    return $env:JAVA_HOME
  }
  $candidates = @(
    (Join-Path ${env:ProgramFiles} "Android\Android Studio\jbr"),
    (Join-Path ${env:ProgramFiles(x86)} "Android\Android Studio\jbr"),
    (Join-Path $env:LOCALAPPDATA "Programs\Android\Android Studio\jbr")
  )
  foreach ($c in $candidates) {
    if ($c -and (Test-Path (Join-Path $c "bin\java.exe"))) { return $c }
  }
  $jdk = Get-ChildItem (Join-Path $env:ProgramFiles "Java") -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
  if ($jdk -and (Test-Path (Join-Path $jdk.FullName "bin\java.exe"))) { return $jdk.FullName }
  return $null
}

$javaHome = Resolve-JavaHome
if ($javaHome) {
  $env:JAVA_HOME = $javaHome
  $env:Path = "$(Join-Path $javaHome 'bin');$env:Path"
  Write-Host "[Env] JAVA_HOME=$javaHome" -ForegroundColor DarkGray
} else {
  Write-Warning "JAVA_HOME non defini et JDK introuvable (installe Android Studio ou un JDK 17+). Gradle ne pourra pas demarrer."
}

function Test-AdbShell {
  param([string] $Serial)
  $old = $ErrorActionPreference
  $ErrorActionPreference = "SilentlyContinue"
  $out = & $script:AdbExe -s $Serial shell getprop ro.product.cpu.abilist 2>&1
  $ErrorActionPreference = $old
  if ($LASTEXITCODE -ne 0) { return $false }
  $text = if ($out -is [array]) { $out -join "`n" } else { "$out" }
  if ($text -match "closed|error:") { return $false }
  if ([string]::IsNullOrWhiteSpace($text)) { return $false }
  return $true
}

if (-not $SkipConnect) {
  Write-Host "[ADB] Redemarrage du serveur..." -ForegroundColor Cyan
  Invoke-AdbQuiet -AdbArguments @("kill-server")
  Start-Sleep -Milliseconds 800
  & $script:AdbExe start-server | Out-Null

  if ($Wireless) {
    Write-Host "[ADB] Connexion $Wireless ..." -ForegroundColor Cyan
    Invoke-AdbQuiet -AdbArguments @("disconnect", $Wireless)
    Start-Sleep -Milliseconds 400
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $script:AdbExe connect $Wireless 2>&1 | Write-Host
    $ErrorActionPreference = $oldEap
    Start-Sleep -Seconds 1
  }
}

Write-Host "[ADB] Appareils:" -ForegroundColor Cyan
& $script:AdbExe devices -l

$lines = & $script:AdbExe devices | Where-Object { $_ -match "`tdevice$" }
$serials = @()
foreach ($line in $lines) {
  $parts = $line -split "`t"
  if ($parts.Count -ge 2 -and $parts[1].Trim() -eq "device") {
    $serials += $parts[0].Trim()
  }
}

if ($serials.Count -eq 0) {
  Write-Error "Aucun appareil en etat 'device'. Branche l'USB ou lance: .\expo-android.ps1 -Wireless 192.168.x.x:5555"
}

$serial = $serials[0]
if ($serials.Count -gt 1) {
  Write-Host "[ADB] Plusieurs appareils; utilisation de: $serial" -ForegroundColor Yellow
}

Write-Host "[ADB] Verification shell (getprop cpu.abilist)..." -ForegroundColor Cyan
$ok = $false
foreach ($attempt in 1..5) {
  if (Test-AdbShell -Serial $serial) {
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $abi = & $script:AdbExe -s $serial shell getprop ro.product.cpu.abilist 2>&1
    $ErrorActionPreference = $oldEap
    Write-Host "  OK ($attempt/5) ABI: $($abi -join '')" -ForegroundColor Green
    $ok = $true
    break
  }
  Write-Host "  Echec tentative $attempt/5, nouvel essai dans 1s..." -ForegroundColor Yellow
  Start-Sleep -Seconds 1
  if ($Wireless -and -not $SkipConnect) {
    Invoke-AdbQuiet -AdbArguments @("connect", $Wireless)
  }
}

if (-not $ok) {
  Write-Error "ADB shell instable sur $serial. Essaye le cable USB ou reconnecte le Wi-Fi (adb connect)."
}

$env:ANDROID_SERIAL = $serial
Write-Host "[Expo] npx expo run:android (ANDROID_SERIAL=$serial)..." -ForegroundColor Cyan
& npx expo run:android @ExpoArgs
