@echo off
REM Wrapper serv1 : test_on_serv1.ps1 search "requete"
if "%~1"=="" (
  echo Usage: test_on_serv1.cmd search "boulangerie metz"
  echo        test_on_serv1.cmd prospect "Hotel des Ventes de Metz"
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_on_serv1.ps1" %*
exit /b %ERRORLEVEL%
