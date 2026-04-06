#Requires -Version 5.1
<#
.SYNOPSIS
  Wrappers sdkmanager (paquets SDK) et avdmanager (emulateurs AVD).
.PARAMETER Action
  list-installed | list-available | install-defaults | uninstall | licenses | list-avd | help
.PARAMETER Packages
  Pour uninstall : ids separes par des virgules, ex. "build-tools;35.0.0"
#>
param(
  [ValidateSet("list-installed", "list-available", "install-defaults", "uninstall", "licenses", "list-avd", "help")]
  [string] $Action = "list-installed",
  [string] $Packages = ""
)

$ErrorActionPreference = "Stop"

function Resolve-JavaHome {
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
if (-not $javaHome) {
  Write-Error "JAVA_HOME introuvable (Android Studio JBR ou JDK)."
}
$env:JAVA_HOME = $javaHome
$env:Path = "$(Join-Path $javaHome 'bin');$env:Path"

$sdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$sdkm = Join-Path $sdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"
$avdm = Join-Path $sdkRoot "cmdline-tools\latest\bin\avdmanager.bat"

if (-not (Test-Path $sdkm)) {
  Write-Error "sdkmanager introuvable: $sdkm`nInstalle 'Android SDK Command-line Tools' (SDK Manager > SDK Tools)."
}

function Invoke-SdkManager {
  param([string[]] $SdkArguments)
  Write-Host "[sdkmanager] sdkmanager $($SdkArguments -join ' ')" -ForegroundColor Cyan
  & $sdkm --sdk_root=$sdkRoot @SdkArguments
}

function Show-Help {
  @"
Usage: .\android-sdk.ps1 -Action <command> [-Packages 'id1,id2']

  list-installed   Paquets SDK deja installes
  list-available   Liste complete des paquets (tres long)
  install-defaults Installe platforms android-36, build-tools 36.0.0 (utile Expo/RN)
  uninstall        Desinstalle les ids dans -Packages (ex: build-tools;35.0.0)
  licenses         Accepte les licences SDK (non interactif)
  list-avd         Liste les emulateurs Android (AVD)
  help             Ce message

Exemples:
  .\android-sdk.ps1 -Action list-installed
  .\android-sdk.ps1 -Action list-avd
  .\android-sdk.ps1 -Action uninstall -Packages 'build-tools;35.0.0'
  .\android-sdk.ps1 -Action install-defaults
"@
}

switch ($Action) {
  "help" { Show-Help; exit 0 }
  "list-installed" {
    Invoke-SdkManager -SdkArguments @("--list_installed")
  }
  "list-available" {
    Invoke-SdkManager -SdkArguments @("--list")
  }
  "install-defaults" {
    Write-Host "Installation: platforms android-36, build-tools 36.0.0" -ForegroundColor Yellow
    Invoke-SdkManager -SdkArguments @("platforms;android-36", "build-tools;36.0.0")
  }
  "uninstall" {
    if (-not $Packages.Trim()) {
      Write-Error "Usage: -Action uninstall -Packages 'build-tools;35.0.0'"
    }
    $ids = $Packages -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    foreach ($id in $ids) {
      Write-Host "Desinstallation: $id" -ForegroundColor Yellow
      Invoke-SdkManager -SdkArguments @("--uninstall", $id)
    }
  }
  "licenses" {
    Write-Host "Acceptation des licences..." -ForegroundColor Yellow
    $yes = "y`n" * 20
    $yes | & $sdkm --sdk_root=$sdkRoot --licenses
  }
  "list-avd" {
    if (-not (Test-Path $avdm)) {
      Write-Error "avdmanager introuvable: $avdm"
    }
    Write-Host "[avdmanager] list avd" -ForegroundColor Cyan
    & $avdm list avd
  }
}
