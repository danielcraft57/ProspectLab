@echo off
REM Lance le deploiement prod sans toucher a la ExecutionPolicy utilisateur (Bypass pour ce processus uniquement).
setlocal
chcp 65001 >nul
set "SCRIPT=%~dp0deploy_production.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
