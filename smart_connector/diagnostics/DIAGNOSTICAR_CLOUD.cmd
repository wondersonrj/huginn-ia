@echo off
title HUGINN - Diagnostico HTTPS
powershell.exe -NoProfile -File "%~dp0Test-HuginnCloud.ps1"
echo.
echo Diagnostico concluido. Nenhuma configuracao de rede foi alterada.
pause
