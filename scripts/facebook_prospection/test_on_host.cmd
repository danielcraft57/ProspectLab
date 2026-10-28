@echo off
REM Wrapper : test_on_host.ps1 search "requete"
if "%~1"=="" (
  echo Usage: test_on_host.cmd search "boulangerie metz"
  echo        test_on_host.cmd prospect "Nom entreprise"
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_on_host.ps1" %*
