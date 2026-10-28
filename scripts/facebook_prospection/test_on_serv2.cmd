@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_on_host.ps1" %*
